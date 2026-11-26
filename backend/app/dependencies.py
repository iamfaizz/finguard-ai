# Compatibility export for the advisor router. Import only after main defines auth.
from .main import current_user as get_current_user
from .database import get_db
