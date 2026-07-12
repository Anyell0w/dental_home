class DashboardController:

    def __init__(self, dao_dashboard):
        self.dao_dashboard = dao_dashboard

    def obtener_estadisticas(self):
        return self.dao_dashboard.obtener_estadisticas()

    def obtener_agenda_hoy(self):
        return self.dao_dashboard.obtener_agenda_hoy()
    

    
    def obtener_actividad_reciente(self):
        return self.dao_dashboard.obtener_actividad_reciente()
