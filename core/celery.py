import os
from celery import Celery

# Establecer el módulo de configuración de Django predeterminado para Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('clanship')

# Leer la configuración de Celery desde settings.py usando el prefijo CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodescubrir tareas en todas las apps instaladas (tasks.py)
app.autodiscover_tasks()

app.conf.imports = (
    'core.tasks',
)

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
