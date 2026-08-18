# Importar la app de Celery para asegurar que se cargue cuando Django inicie
from .celery import app as celery_app

__all__ = ('celery_app',)
