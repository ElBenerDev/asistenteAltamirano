# Parte 1: Importaciones y configuración inicial
import os
import json
import asyncio
import logging
import time
from datetime import datetime
from threading import Lock
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
from openai import OpenAI
import pytz
from dotenv import load_dotenv
from db_handler import NeonDatabaseHandler


# Configuración básica
load_dotenv()

class ConversationState(Enum):
    INITIAL = "initial"
    COLLECTING_INFO = "collecting_info"
    SCHEDULING_APPOINTMENT = "scheduling_appointment" 
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class ContactInfo:
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'email': self.email,
            'phone': self.phone
        }

    def is_complete(self) -> bool:
        return all([self.name, self.email, self.phone])

def setup_logging() -> logging.Logger:
    """Configura el sistema de logging"""
    logger = logging.getLogger('dental_assistant')
    logger.setLevel(logging.DEBUG)
    
    if not logger.handlers:
        # File handler
        file_handler = logging.FileHandler('dental_assistant.log')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(
            logging.Formatter('%(levelname)s: %(message)s')
        )
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger

# Inicializar logger
logger = setup_logging()

# Definición de las tools del asistente
ASSISTANT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "extract_contact_info",
            "description": "Extrae la información de contacto del mensaje del usuario",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Nombre completo del usuario"
                    },
                    "email": {
                        "type": "string",
                        "description": "Correo electrónico del usuario"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Número de teléfono del usuario (10 dígitos)"
                    }
                },
                "required": ["name", "email", "phone"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_lead",
            "description": "Crea un lead en la base de datos",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Nombre completo del usuario"
                    },
                    "email": {
                        "type": "string",
                        "description": "Correo electrónico del usuario"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Número de teléfono del usuario"
                    }
                },
                "required": ["name", "email", "phone"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_appointment_date",
            "description": "Valida si una fecha y hora son válidas para una cita",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Fecha en formato YYYY-MM-DD"
                    },
                    "time": {
                        "type": "string",
                        "description": "Hora en formato HH:MM"
                    }
                },
                "required": ["date", "time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_appointment",
            "description": "Crea una nueva cita dental",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Nombre completo del paciente"
                    },
                    "email": {
                        "type": "string",
                        "description": "Correo electrónico del paciente"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Número de teléfono del paciente"
                    },
                    "service_type": {
                        "type": "string",
                        "description": "Tipo de servicio dental",
                        "enum": ["CONSULTA", "LIMPIEZA", "TRATAMIENTO"]
                    },
                    "date": {
                        "type": "string",
                        "description": "Fecha de la cita en formato YYYY-MM-DD"
                    },
                    "time": {
                        "type": "string",
                        "description": "Hora de la cita en formato HH:MM"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Notas adicionales para la cita"
                    }
                },
                "required": ["name", "email", "phone", "service_type", "date", "time"]
            }
        }
    }
]

# Parte 2: Clases principales y configuración

class Config:
    """Configuración centralizada del asistente"""
    ARGENTINA_TZ = pytz.timezone('America/Argentina/Buenos_Aires')
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ASSISTANT_ID = None  # Inicializamos como None

    @classmethod
    def get_or_create_assistant_id(cls) -> str:
        """Obtiene o crea el ID del asistente"""
        try:
            # Si ya tenemos un ID, lo devolvemos
            if cls.ASSISTANT_ID:
                return cls.ASSISTANT_ID

            # Intentamos obtener el ID del ambiente
            env_assistant_id = os.getenv("DENTAL_ASSISTANT_ID")
            if env_assistant_id:
                cls.ASSISTANT_ID = env_assistant_id
                return cls.ASSISTANT_ID

            # Si no existe, creamos un nuevo asistente
            client = OpenAI(api_key=cls.OPENAI_API_KEY)
            assistant = client.beta.assistants.create(
                name="Facilitador Migratorio Laura",
                instructions = """Eres Laura, la asistente virtual de Immigration Help México.
                Tu tarea es ayudar a los interesados en los servicios migratorios a agendar una cita.
                Nuestras oficinas se encuentran frente a las oficinas de migración en playa del carmen..

                Proceso de programación de citas:
                1. Pide el nombre, correo y teléfono si no los tienes
                2. Pregunta qué tipo de servicio necesitan  (Residencia temporal, Residencia Permanente, Pasaporte)
                3. Pide la fecha y hora preferida
                4. Valida la fecha y hora usando validate_appointment_date
                5. Si la fecha es válida, crea la cita usando create_appointment

                Reglas importantes:
                1. Responderás según el idioma con el que te hable el cliente
                2. siempre Sé amable y profesional
                3. Verifica la disponibilidad ANTES de crear la cita
                4. Si una fecha no está disponible, sugiere horarios cercanos
                5. Horario de atención: Lunes a Viernes de 9:00 a 18:00
                6. Duración por defecto de las citas: 30 minutos

                Formato de fechas y horas:
                - Fecha: YYYY-MM-DD (ejemplo: 2024-02-01)
                - Hora: HH:MM (ejemplo: 14:30)""",
                model="gpt-3.5-turbo",
                tools=ASSISTANT_TOOLS
            )
            cls.ASSISTANT_ID = assistant.id
            logger.info(f"Created new assistant with ID: {cls.ASSISTANT_ID}")
            return cls.ASSISTANT_ID

        except Exception as e:
            logger.error(f"Error in get_or_create_assistant_id: {str(e)}")
            raise

class ConversationManager:
    def __init__(self):
        self.threads: Dict[str, Dict] = {}
        self.lock = Lock()
        self.logger = logging.getLogger('dental_assistant')
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.db_handler = NeonDatabaseHandler()

    def get_thread(self, user_id: str) -> Dict:
        with self.lock:
            if user_id in self.threads:
                return self.threads[user_id]

            try:
                # Crear nuevo thread en OpenAI
                thread = self.client.beta.threads.create()
                
                # Intentar obtener el contexto existente de la base de datos
                context_result = self.db_handler.get_context(user_id)
                
                if context_result.get("success"):
                    context = context_result.get("context", {})
                else:
                    # Asegurar que tenemos la estructura correcta del contexto
                    context = {
                        'contact_info': {
                            'name': None,
                            'email': None,
                            'phone': None
                        },
                        'state': 'initial',
                        'appointment_details': {}
                    }

                thread_data = {
                    'thread_id': thread.id,
                    'context': context
                }
                self.threads[user_id] = thread_data
                return thread_data

            except Exception as e:
                self.logger.error(f"Error creating thread: {e}")
                raise
                
            
    def update_context(self, user_id: str, updates: Dict[str, Any]) -> None:
        """Actualiza el contexto de un thread"""
        with self.lock:
            if user_id in self.threads:
                thread_data = self.threads[user_id]
                
                if 'contact_info' in updates:
                    current_info = thread_data['context'].get('contact_info', {})
                    current_info.update(updates['contact_info'])
                    thread_data['context']['contact_info'] = current_info
                
                for key, value in updates.items():
                    if key != 'contact_info':
                        thread_data['context'][key] = value
                
                # Guardar el contexto actualizado en la base de datos
                self.db_handler.save_context(user_id, thread_data['context'])
                
                self.logger.debug(f"Updated context for user {user_id}: {updates}")

    def create_lead(self, lead_data: dict, user_id: str = None) -> Dict[str, Any]:
        try:
            # Crear el lead en la base de datos
            result = self.db_handler.create_lead(lead_data)
            
            if result.get("success"):
                # Actualizar el contexto con la información del lead
                if user_id:
                    self.update_context(user_id, {
                        'state': ConversationState.COLLECTING_INFO.value,  # Usar el estado correcto
                        'contact_info': {
                            'name': lead_data.get('name'),
                            'email': lead_data.get('email'),
                            'phone': lead_data.get('phone')
                        },
                        'lead_id': result.get('lead_id')
                    })
                
                return {
                    "success": True,
                    "message": "Lead creado exitosamente",
                    "lead_id": result.get("lead_id")
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Error desconocido al crear el lead")
                }
        except Exception as e:
            self.logger.error(f"Error creating lead: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def handle_message(self, user_id: str, message: str) -> Dict[str, Any]:
        """Maneja un mensaje del usuario"""
        try:
            thread_data = self.get_thread(user_id)
            thread_id = thread_data['thread_id']

            # Verificar si hay runs activos
            runs = self.client.beta.threads.runs.list(thread_id=thread_id)
            active_runs = [run for run in runs.data if run.status in ['in_progress', 'queued']]

            if active_runs:
                # Si hay un run activo, esperar hasta 15 segundos
                run = active_runs[0]
                max_wait = 15
                wait_count = 0
                
                while wait_count < max_wait:
                    run_status = self.client.beta.threads.runs.retrieve(
                        thread_id=thread_id,
                        run_id=run.id
                    )
                    
                    if run_status.status in ['completed', 'failed', 'expired', 'cancelled']:
                        break
                        
                    time.sleep(1)
                    wait_count += 1
                
                if wait_count >= max_wait:
                    return {
                        "type": "text",
                        "content": "Estoy procesando tu mensaje anterior. Por favor, espera un momento antes de enviar otro mensaje."
                    }

            # Si no hay runs activos o el run anterior terminó, proceder con el nuevo mensaje
            try:
                message_response = self.client.beta.threads.messages.create(
                    thread_id=thread_id,
                    role="user",
                    content=message
                )
            except Exception as e:
                if "while a run is active" in str(e):
                    return {
                        "type": "text",
                        "content": "Aún estoy procesando tu mensaje anterior. Por favor, espera unos segundos y vuelve a intentarlo."
                    }
                raise

            # Asegurarnos de tener un assistant_id válido
            assistant_id = Config.get_or_create_assistant_id()
            if not assistant_id:
                raise ValueError("No se pudo obtener el ID del asistente")

            # Crear y ejecutar el run
            run = self.client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=assistant_id
            )

            return self._process_run(thread_id, run.id, user_id)

        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}")
            return {
                "type": "error",
                "content": "Error al procesar tu mensaje. Por favor, intenta nuevamente en unos momentos."
            }

    def _process_run(self, thread_id: str, run_id: str, user_id: str) -> Dict[str, Any]:
        """Procesa un run con backoff exponencial"""
        try:
            max_retries = 10
            base_delay = 1
            
            for attempt in range(max_retries):
                try:
                    run = self.client.beta.threads.runs.retrieve(
                        thread_id=thread_id,
                        run_id=run_id
                    )
                    
                    if run.status == 'completed':
                        messages = self.client.beta.threads.messages.list(thread_id=thread_id)
                        return {
                            "type": "text",
                            "content": messages.data[0].content[0].text.value
                        }
                        
                    elif run.status == 'requires_action':
                        tool_outputs = []
                        for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                            result = self._handle_tool_call(tool_call, user_id)
                            if result:
                                tool_outputs.append({
                                    "tool_call_id": tool_call.id,
                                    "output": json.dumps(result)
                                })

                        if tool_outputs:
                            self.client.beta.threads.runs.submit_tool_outputs(
                                thread_id=thread_id,
                                run_id=run_id,
                                tool_outputs=tool_outputs
                            )
                            continue
                    
                    elif run.status in ['failed', 'expired', 'cancelled']:
                        raise Exception(f"Run failed with status: {run.status}")
                    
                    # Backoff exponencial
                    delay = base_delay * (2 ** attempt)
                    time.sleep(min(delay, 4))  # Máximo 4 segundos de espera
                    
                except Exception as e:
                    self.logger.error(f"Error in run iteration: {str(e)}")
                    delay = base_delay * (2 ** attempt)
                    time.sleep(min(delay, 4))
                    continue
                
            raise TimeoutError("Run processing timed out")
                
        except Exception as e:
            self.logger.error(f"Error processing run: {str(e)}")
            return {
                "type": "error",
                "content": "Error al procesar tu mensaje. Por favor, intenta nuevamente."
            }
            

    def _handle_tool_call(self, tool_call: Any, user_id: str) -> Optional[Dict]:
        try:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            if function_name == "extract_contact_info":
                # Actualizar solo la parte de contact_info en el contexto existente
                contact_info = {
                    'name': function_args.get('name'),
                    'email': function_args.get('email'),
                    'phone': function_args.get('phone')
                }
                
                # Actualizar el contexto
                self.update_context(user_id, {
                    'contact_info': contact_info,
                    'state': ConversationState.COLLECTING_INFO.value
                })
                
                # Crear el lead si tenemos toda la información
                if all([
                    contact_info.get('name'),
                    contact_info.get('email'),
                    contact_info.get('phone')
                ]):
                    try:
                        lead_result = self.create_lead(contact_info, user_id)
                        if not lead_result.get("success"):
                            self.logger.error(f"Error creating lead: {lead_result.get('error')}")
                    except Exception as e:
                        self.logger.error(f"Error creating lead: {str(e)}")
                
                return {
                    "success": True,
                    "message": "Información de contacto procesada correctamente"
                }
                    
            elif function_name == "validate_appointment_date":
                try:
                    result = self.validate_appointment_date(
                        function_args.get('date'),
                        function_args.get('time'),
                        user_id
                    )
                    return result
                except Exception as e:
                    self.logger.error(f"Error validating appointment: {str(e)}")
                    return {
                        "success": False,
                        "error": "No se pudo validar la fecha. Por favor, intenta nuevamente."
                    }
                    
            elif function_name == "create_appointment":
                try:
                    thread_data = self.get_thread(user_id)
                    contact_info = thread_data.get('context', {}).get('contact_info', {})
                    
                    appointment_data = {
                        **function_args,
                        "name": contact_info.get('name'),
                        "email": contact_info.get('email'),
                        "phone": contact_info.get('phone'),
                    }
                    
                    result = self.create_appointment(appointment_data)
                    if result.get("success"):
                        self.update_context(user_id, {
                            'state': ConversationState.SCHEDULING_APPOINTMENT.value,
                            'appointment_details': {
                                'date': function_args.get('date'),
                                'time': function_args.get('time'),
                                'appointment_id': result.get('appointment_id')
                            }
                        })
                    return result
                except Exception as e:
                    self.logger.error(f"Error creating appointment: {str(e)}")
                    return {
                        "success": False,
                        "error": "Error al crear la cita. Por favor, intenta nuevamente."
                    }
                        
            return {"success": False, "error": "Operación no soportada"}
                        
        except Exception as e:
            self.logger.error(f"Error in tool call {tool_call.function.name}: {str(e)}")
            return {
                "success": False,
                "error": "Error al procesar la operación. Por favor, intenta nuevamente."
            }
        
    def parse_date_time(self, date_time_str: str) -> Tuple[str, str]:
        """Parsea una cadena de fecha y hora"""
        try:
            # Limpiar la entrada
            date_time_str = date_time_str.strip()
            # Si contiene coma, dividir por coma
            if ',' in date_time_str:
                parts = date_time_str.split(',')
            else:
                # Si no contiene coma, dividir por espacio
                parts = date_time_str.split(' ')
            
            # Limpiar espacios en blanco
            date_str = parts[0].strip()
            time_str = parts[1].strip() if len(parts) > 1 else ""
            
            return date_str, time_str
            
        except Exception as e:
            self.logger.error(f"Error parsing date time: {str(e)}")
            raise ValueError("Formato de fecha y hora inválido")

    def validate_appointment_date(self, date: str, time: str, user_id: str = None) -> Dict[str, Any]:
        try:
            # Parsear fecha y hora si vienen juntas
            if ',' in date:
                date, time = self.parse_date_time(date)
            
            # Obtener el contexto del usuario y verificar la información
            thread_data = self.get_thread(user_id) if user_id else {}
            context = thread_data.get('context', {})
            contact_info = context.get('contact_info', {})

            # Verificar si tenemos la información necesaria del paciente
            if not contact_info or not contact_info.get('name'):
                return {
                    "success": False,
                    "error": "missing_patient_info",
                    "message": "Necesito tu información personal antes de agendar la cita. Por favor, proporciona tu nombre completo."
                }
                
            # Convertir strings a datetime
            date_obj = datetime.strptime(date.strip(), "%Y-%m-%d").date()
            time_obj = datetime.strptime(time.strip(), "%H:%M").time()
            appointment_datetime = datetime.combine(date_obj, time_obj)
            
            # Obtener la hora actual en Argentina
            argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
            current_datetime = datetime.now(argentina_tz).replace(tzinfo=None)

            # Validaciones
            if appointment_datetime < current_datetime:
                return {
                    "success": False,
                    "error": "La fecha y hora seleccionada ya pasó"
                }

            if appointment_datetime.weekday() >= 5:  # 5 = Sábado, 6 = Domingo
                return {
                    "success": False,
                    "error": "Solo atendemos de Lunes a Viernes"
                }

            if time_obj.hour < 9 or time_obj.hour >= 18:
                return {
                    "success": False,
                    "error": "Nuestro horario de atención es de 9:00 a 18:00"
                }

            # Verificar disponibilidad usando el db_handler
            availability = self.db_handler.check_availability(date, time)
            
            if not availability.get("success"):
                return {
                    "success": False,
                    "error": "Error al verificar disponibilidad"
                }

            if not availability.get("available"):
                return {
                    "success": False,
                    "error": "El horario seleccionado no está disponible"
                }

            # Si todo está bien y tenemos un user_id, crear el paciente y la cita
            if user_id:
                # Primero crear el paciente
                patient_data = {
                    "name": contact_info['name'],
                    "email": contact_info.get('email'),
                    "phone": contact_info.get('phone', user_id),
                    "notes": "Paciente creado a través de WhatsApp"
                }

                # Crear el paciente
                patient_result = self.db_handler.create_patient(patient_data)
                
                if not patient_result.get("success"):
                    return {
                        "success": False,
                        "error": f"Error al crear el paciente: {patient_result.get('error', 'Error desconocido')}"
                    }

                # Preparar los datos de la cita
                appointment_data = {
                    "name": contact_info['name'],
                    "email": contact_info.get('email'),
                    "phone": contact_info.get('phone'),
                    "date": date,
                    "time": time,
                    "service_type": context.get('service_type', "CONSULTA"),  # Usar el tipo de servicio del contexto
                    "duration": 30
                }

                result = self.db_handler.create_appointment(appointment_data)
                
                if result.get("success"):
                    # Actualizar el contexto con la información de la cita
                    self.update_context(user_id, {
                        'state': ConversationState.SCHEDULING_APPOINTMENT.value,
                        'appointment_details': {
                            'date': date,
                            'time': time,
                            'appointment_id': result.get('appointment_id'),
                            'patient_id': patient_result.get('patient_id')
                        }
                    })
                    return {
                        "success": True,
                        "message": "Cita agendada exitosamente"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Error al crear la cita: {result.get('error', 'Error desconocido')}"
                    }

            return {
                "success": True,
                "message": "Fecha y hora disponibles para agendar"
            }

        except ValueError as e:
            self.logger.error(f"Error de formato: {str(e)}")
            return {
                "success": False,
                "error": "Formato de fecha u hora inválido. Use YYYY-MM-DD para fecha y HH:MM para hora"
            }
        except Exception as e:
            self.logger.error(f"Error validando fecha de cita: {str(e)}")
            return {
                "success": False,
                "error": f"Error al validar la fecha y hora: {str(e)}"
            }
            
    def create_appointment(self, appointment_data: dict) -> dict:
        """
        Crea una nueva cita usando el db_handler
        """
        try:
            return self.db_handler.create_appointment(appointment_data)
        except Exception as e:
            self.logger.error(f"Error creating appointment: {str(e)}")
            return {"success": False, "error": str(e)}
                    
# Parte 3: Métodos de manejo de mensajes y asistente
class DentalAssistant:
    def __init__(self):
        self.conversation_manager = ConversationManager()
        self.logger = logging.getLogger('dental_assistant')
        # Asegurarnos de que tenemos un assistant_id
        Config.ASSISTANT_ID = Config.get_or_create_assistant_id()
        if not Config.ASSISTANT_ID:
            raise ValueError("No se pudo obtener o crear el ID del asistente")

    def handle_message(self, user_id: str, message: str) -> Dict[str, Any]:  # Quitar async aquí
        try:
            return self.conversation_manager.handle_message(user_id, message)
        except Exception as e:
            self.logger.error(f"Error handling message: {str(e)}")
            return {
                "type": "error",
                "content": "Error al procesar tu mensaje. Por favor, intenta nuevamente."
            }


# Parte 4: Funciones de inicialización y código principal

dental_assistant = None

async def initialize_assistant() -> bool:
    """Inicializa el asistente dental"""
    global dental_assistant
    try:
        dental_assistant = DentalAssistant()  # Ya no necesita db_handler
        logger.info("Asistente dental inicializado correctamente")
        return True
    except Exception as e:
        logger.error(f"Error inicializando el asistente: {str(e)}")
        return False

async def handle_assistant_response(
    message: str, 
    user_id: str, 
    user_context: Optional[Dict] = None
) -> Tuple[Optional[str], Optional[str]]:
    try:
        logger.info(f"Processing message for user {user_id}: {message}")
        
        if not dental_assistant:
            if not await initialize_assistant():
                return None, "Error inicializando el asistente"

        if user_context and dental_assistant:
            # Quitar await aquí porque update_context no es async
            dental_assistant.conversation_manager.update_context(user_id, user_context)

        # Quitar await aquí porque handle_message no es async
        response = dental_assistant.handle_message(user_id, message)
        
        if response["type"] == "text":
            # Quitar await aquí porque get_thread no es async
            thread_data = dental_assistant.conversation_manager.get_thread(user_id)
            if thread_data['context'].get('state') == ConversationState.COMPLETED.value:
                logger.info(f"Lead process completed for user {user_id}")
            return response["content"], None
        else:
            logger.error(f"Error en la respuesta: {response['content']}")
            return None, response["content"]

    except Exception as e:
        logger.error(f"Error en handle_assistant_response: {str(e)}")
        return None, str(e)

async def cleanup_resources():
    """Limpia los recursos antes de cerrar"""
    try:
        if dental_assistant:
            logger.info("Limpiando recursos...")
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

def run_async(func: Any, *args: Any) -> Any:
    """Ejecuta una función asíncrona en un nuevo event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(func(*args))
    finally:
        loop.close()

async def main():
    """Función principal para pruebas"""
    try:
        print("Inicializando asistente dental...")
        if await initialize_assistant():
            print("¡Hola! Soy Laura, tu asistente dental. ¿En qué puedo ayudarte?")
            test_user_id = f"test_user_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            while True:
                try:
                    user_input = input("Tú: ").strip()
                    if user_input.lower() in ["salir", "exit", "quit"]:
                        print("¡Hasta luego! Que tengas un excelente día.")
                        break
                    
                    response, error = await handle_assistant_response(user_input, test_user_id)
                    if error:
                        print(f"Error: {error}")
                    else:
                        print(f"Laura: {response}")

                except KeyboardInterrupt:
                    print("\nCerrando el asistente...")
                    break
                except Exception as e:
                    print(f"Error: {str(e)}")
                    continue

    except Exception as e:
        print(f"Error crítico: {str(e)}")
    finally:
        await cleanup_resources()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nPrograma terminado por el usuario")
    except Exception as e:
        print(f"Error fatal: {str(e)}")