from collections import defaultdict
from odoo import models, api

class FieldVisitDashboard(models.Model):
    _inherit = 'field.visit'

    @api.model
    def retrieve_dashboard(self, date_from=False, date_to=False):
        domain = []
        if date_from:
            domain.append(('date_start', '>=', date_from))
        if date_to:
            domain.append(('date_start', '<=', date_to))

        visits = self.search(domain)

        visit_data = defaultdict(int)
        for visit in visits:
            for user in visit.user_id:
                visit_data[user.name] += 1

        result = [{'salesperson': k, 'visit_count': v} for k, v in visit_data.items()]
        print("field visit: %s",result)
        return result