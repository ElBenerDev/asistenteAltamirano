#!/bin/bash


echo "Verificando instalación de SQLAlchemy..."
python -c "import sqlalchemy; print(f'SQLAlchemy instalado correctamente: {sqlalchemy.__version__}')" || exit 1

echo "Iniciando servidor Gunicorn..."
gunicorn app:app --bind 127.0.0.1:5000 --workers 1 --timeout 120