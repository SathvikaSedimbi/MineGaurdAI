class WeatherEngine:
    def __init__(self):
        # All percentages are 0.0 to 100.0
        self.rain_intensity = 0.0
        self.wind_speed = 5.0  # km/h
        self.fog_density = 0.0
        self.humidity = 45.0
        self.dust_level = 10.0
        self.cloud_cover = 5.0
        
    def update_weather(self, rain=None, wind=None, fog=None, humidity=None, dust=None, clouds=None):
        if rain is not None:
            self.rain_intensity = max(0.0, min(100.0, float(rain)))
        if wind is not None:
            self.wind_speed = max(0.0, min(120.0, float(wind)))
        if fog is not None:
            self.fog_density = max(0.0, min(100.0, float(fog)))
        if humidity is not None:
            self.humidity = max(0.0, min(100.0, float(humidity)))
        if dust is not None:
            self.dust_level = max(0.0, min(100.0, float(dust)))
        if clouds is not None:
            self.cloud_cover = max(0.0, min(100.0, float(clouds)))
            
    def get_state(self):
        return {
            "rain": self.rain_intensity,
            "wind": self.wind_speed,
            "fog": self.fog_density,
            "humidity": self.humidity,
            "dust": self.dust_level,
            "clouds": self.cloud_cover
        }
