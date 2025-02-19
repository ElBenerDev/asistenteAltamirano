from sqlalchemy import create_engine, text
from datetime import datetime
import logging
import json
import time
from typing import Dict, Any


class NeonDatabaseHandler:
    def __init__(self, db=None):
        self.logger = logging.getLogger(__name__)
        self.db = db
        # Agregar configuración de retry y timeout
        self.engine = create_engine(
            "postgresql://neondb_owner:npg_mTJhLZ5FtRA3@ep-little-term-a8x9ojn0-pooler.eastus2.azure.neon.tech/neondb",
            connect_args={
                "sslmode": "require",
                "connect_timeout": 10,
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5
            },
            pool_pre_ping=True,
            pool_recycle=300,
            pool_timeout=30
        )


    def create_lead(self, lead_data: dict) -> dict:
        """Crea un lead en la base de datos"""
        try:
            if not lead_data.get("name"):
                return {"success": False, "error": "El nombre es requerido"}

            with self.engine.connect() as connection:
                with connection.begin():
                    query = text("""
                        INSERT INTO leads (
                            name,
                            email,
                            phone,
                            source,
                            status,
                            notes,
                            created_at,
                            updated_at
                        ) VALUES (
                            :name,
                            :email,
                            :phone,
                            :source,
                            :status,
                            :notes,
                            :created_at,
                            :updated_at
                        ) RETURNING id
                    """)
                    
                    result = connection.execute(
                        query,
                        {
                            "name": lead_data.get("name"),
                            "email": lead_data.get("email"),
                            "phone": lead_data.get("phone"),
                            "source": "WhatsApp",
                            "status": "NUEVO",
                            "notes": lead_data.get("notes", "Contacto inicial por WhatsApp"),
                            "created_at": datetime.utcnow(),
                            "updated_at": datetime.utcnow()
                        }
                    )
                    lead_id = result.scalar()
                    
                    return {"success": True, "lead_id": lead_id}

        except Exception as e:
            self.logger.error(f"Error creating lead: {str(e)}")
            return {"success": False, "error": str(e)}

    def create_patient(self, patient_data: dict) -> dict:
        """
        Crea un nuevo paciente en la base de datos
        """
        try:
            if not patient_data.get("name"):
                return {"success": False, "error": "El nombre es requerido"}

            with self.engine.connect() as connection:
                with connection.begin():
                    query = text("""
                        INSERT INTO patients (
                            name,
                            email,
                            phone,
                            notes,
                            created_at,
                            updated_at
                        ) VALUES (
                            :name,
                            :email,
                            :phone,
                            :notes,
                            :created_at,
                            :updated_at
                        ) RETURNING id
                    """)
                    
                    result = connection.execute(
                        query,
                        {
                            "name": patient_data.get("name"),
                            "email": patient_data.get("email"),
                            "phone": patient_data.get("phone"),
                            "notes": patient_data.get("notes", "Paciente creado por WhatsApp"),
                            "created_at": datetime.utcnow(),
                            "updated_at": datetime.utcnow()
                        }
                    )
                    patient_id = result.scalar()
                    
                    return {"success": True, "patient_id": patient_id}

        except Exception as e:
            self.logger.error(f"Error al crear paciente: {str(e)}")
            return {"success": False, "error": str(e)}

    def create_appointment(self, appointment_data: dict) -> dict:
        """
        Crea una nueva cita en la base de datos
        """
        try:
            # Validar datos requeridos
            required_fields = ['name', 'date', 'time']
            for field in required_fields:
                if not appointment_data.get(field):
                    return {"success": False, "error": f"El campo {field} es requerido"}

            with self.engine.connect() as connection:
                with connection.begin():
                    # Primero crear o actualizar el paciente
                    patient_result = self.create_patient({
                        "name": appointment_data.get("name"),
                        "email": appointment_data.get("email"),
                        "phone": appointment_data.get("phone")
                    })

                    if not patient_result.get("success"):
                        return {"success": False, "error": f"Error al crear el paciente: {patient_result.get('error')}"}

                    # Combinar fecha y hora en datetime
                    appointment_datetime = datetime.strptime(
                        f"{appointment_data['date']} {appointment_data['time']}", 
                        "%Y-%m-%d %H:%M"
                    )

                    # Verificar disponibilidad antes de crear la cita
                    availability = self.check_availability(
                        appointment_data['date'],
                        appointment_data['time']
                    )
                    if not availability.get("available"):
                        return {"success": False, "error": "El horario seleccionado no está disponible"}

                    query = text("""
                        INSERT INTO appointments (
                            patient_id,
                            datetime,
                            service_type,
                            duration,
                            status,
                            notes,
                            created_at,
                            updated_at
                        ) VALUES (
                            :patient_id,
                            :datetime,
                            :service_type,
                            :duration,
                            :status,
                            :notes,
                            :created_at,
                            :updated_at
                        ) RETURNING id
                    """)
                    
                    result = connection.execute(
                        query,
                        {
                            "patient_id": patient_result["patient_id"],
                            "datetime": appointment_datetime,
                            "service_type": appointment_data.get("service_type", "CONSULTA"),
                            "duration": appointment_data.get("duration", 30),
                            "status": "SCHEDULED",
                            "notes": appointment_data.get("notes", "Cita programada por WhatsApp"),
                            "created_at": datetime.utcnow(),
                            "updated_at": datetime.utcnow()
                        }
                    )
                    appointment_id = result.scalar()
                    
                    return {
                        "success": True, 
                        "appointment_id": appointment_id,
                        "patient_id": patient_result["patient_id"]
                    }

        except Exception as e:
            self.logger.error(f"Error al crear cita: {str(e)}")
            return {"success": False, "error": str(e)}

    def check_availability(self, date: str, time: str) -> dict:
        """
        Verifica si hay disponibilidad para una fecha y hora específica
        """
        try:
            # Combinar fecha y hora
            datetime_str = f"{date} {time}"
            appointment_datetime = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
            
            # Validar horario de atención
            hour = appointment_datetime.hour
            if hour < 9 or hour >= 18:
                return {
                    "success": True,
                    "available": False,
                    "reason": "Fuera de horario de atención (9:00-18:00)"
                }
            
            # Validar días laborables
            if appointment_datetime.weekday() >= 5:  # 5 = Sábado, 6 = Domingo
                return {
                    "success": True,
                    "available": False,
                    "reason": "No atendemos en fin de semana"
                }

            with self.engine.connect() as connection:
                query = text("""
                    SELECT COUNT(*) 
                    FROM appointments 
                    WHERE datetime = :datetime
                    AND status != 'CANCELLED'
                """)
                
                result = connection.execute(
                    query,
                    {"datetime": appointment_datetime}
                )
                count = result.scalar()
                
                return {
                    "success": True,
                    "available": count == 0,
                    "reason": "Horario no disponible" if count > 0 else None
                }

        except Exception as e:
            self.logger.error(f"Error checking availability: {str(e)}")
            return {"success": False, "error": str(e)}
        
    # ... (mantener las importaciones y el inicio de la clase igual)

    def save_context(self, user_id: str, context: dict) -> dict:
        """Guarda o actualiza el contexto del usuario en la base de datos"""
        try:
            with self.engine.connect() as connection:
                with connection.begin():
                    context_json = json.dumps(context)
                    
                    query = text("""
                        INSERT INTO user_context (user_id, context_data, updated_at)
                        VALUES (:user_id, :context_data::jsonb, :updated_at)
                        ON CONFLICT (user_id) 
                        DO UPDATE SET 
                            context_data = :context_data::jsonb,
                            updated_at = :updated_at
                    """)
                    
                    connection.execute(
                        query,
                        {
                            "user_id": user_id,
                            "context_data": context_json,
                            "updated_at": datetime.utcnow()
                        }
                    )
                    
                    # Verificar que se guardó correctamente
                    verify_query = text("""
                        SELECT context_data FROM user_context 
                        WHERE user_id = :user_id
                    """)
                    result = connection.execute(verify_query, {"user_id": user_id})
                    row = result.fetchone()
                    
                    if row and row[0]:
                        return {"success": True}
                        
                    return {"success": False, "error": "No se pudo verificar el guardado del contexto"}

        except Exception as e:
            self.logger.error(f"Error saving context: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_context(self, user_id: str) -> dict:
        """Obtiene el contexto del usuario desde la base de datos"""
        try:
            with self.engine.connect() as connection:
                query = text("""
                    SELECT context_data 
                    FROM user_context 
                    WHERE user_id = :user_id
                """)
                
                result = connection.execute(
                    query,
                    {"user_id": user_id}
                )
                row = result.fetchone()
                
                if row:
                    return {
                        "success": True,
                        "context": json.loads(row[0]) if isinstance(row[0], str) else row[0]
                    }
                return {
                    "success": True,
                    "context": {
                        'contact_info': {'name': None, 'email': None, 'phone': None},
                        'state': 'initial',
                        'appointment_details': {}
                    }
                }

        except Exception as e:
            self.logger.error(f"Error getting context: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_context(self, user_id: str) -> dict:
        """Obtiene el contexto del usuario desde la base de datos"""
        try:
            with self.engine.connect() as connection:
                query = text("""
                    SELECT context_data::text
                    FROM user_context 
                    WHERE user_id = :user_id
                """)
                
                result = connection.execute(
                    query,
                    {"user_id": user_id}
                )
                row = result.fetchone()
                
                if row and row[0]:
                    # El contexto viene como string JSON, lo convertimos a dict
                    return {
                        "success": True,
                        "context": json.loads(row[0])
                    }
                
                # Si no hay contexto, devolver uno por defecto
                return {
                    "success": True,
                    "context": {
                        'contact_info': {'name': None, 'email': None, 'phone': None},
                        'state': 'initial',
                        'appointment_details': {}
                    }
                }

        except Exception as e:
            self.logger.error(f"Error getting context: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_context(self, user_id: str) -> dict:
        """Obtiene el contexto del usuario desde la base de datos"""
        try:
            with self.engine.connect() as connection:
                query = text("""
                    SELECT context_data 
                    FROM user_context 
                    WHERE user_id = :user_id
                """)
                
                result = connection.execute(
                    query,
                    {"user_id": user_id}
                )
                row = result.fetchone()
                
                if row:
                    return {
                        "success": True,
                        "context": json.loads(row[0])
                    }
                return {
                    "success": True,
                    "context": {
                        'contact_info': {'name': None, 'email': None, 'phone': None},
                        'state': 'initial',
                        'appointment_details': {}
                    }
                }

        except Exception as e:
            self.logger.error(f"Error getting context: {str(e)}")
            return {"success": False, "error": str(e)}