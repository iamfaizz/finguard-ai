import os

class Settings:
    @property
    def ml_forecast_url(self):
        return os.getenv("FORECAST_URL", "http://ml-forecast:8000").rstrip("/")

settings = Settings()
