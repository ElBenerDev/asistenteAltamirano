# check_deps.py
def check_dependencies():
    try:
        import sqlalchemy
        print(f"SQLAlchemy instalado: {sqlalchemy.__version__}")
    except ImportError as e:
        print(f"Error importando SQLAlchemy: {e}")

    try:
        import flask
        print(f"Flask instalado: {flask.__version__}")
    except ImportError as e:
        print(f"Error importando Flask: {e}")

    try:
        import openai
        print(f"OpenAI instalado: {openai.__version__}")
    except ImportError as e:
        print(f"Error importando OpenAI: {e}")

if __name__ == "__main__":
    check_dependencies()