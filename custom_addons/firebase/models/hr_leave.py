from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class ResourceCalendarLeaves(models.Model):
    _inherit = 'resource.calendar.leaves'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)

        company_ids = res.mapped('company_id.id')  # Get unique company IDs

        if company_ids:
            employees = self.env['hr.employee'].search([('company_id', 'in', company_ids)])
            valid_user_ids = employees.mapped('user_id').filtered(lambda u: u.device_token).mapped('id')
            payload = {
                'model': 'resource.calendar.leaves',
                'record_id': str(res[0].id),  # Use first record's ID for payload
                'action': 'holiday_added',
                'silent': 'true'
            }
            
            if valid_user_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=valid_user_ids,
                    title=None,
                    body=None,
                    payload={
                        'model': 'resource.calendar.leaves',
                        'record_id': str(res[0].id),  # Use first record's ID for payload
                        'action': 'holiday_added',
                        'silent': 'true'
                    }
                )
            

        return res

    def write(self, vals):
        """Send notification when a public holiday is updated."""
        res = super().write(vals)

        company_ids = self.mapped('company_id.id')  # Get unique company IDs

        if company_ids:
            employees = self.env['hr.employee'].search([('company_id', 'in', company_ids)])
            valid_user_ids = employees.mapped('user_id').filtered(lambda u: u.device_token).mapped('id')
            payload = {
                'model': 'resource.calendar.leaves',
                'record_id': str(self[0].id),  # Use first record's ID for payload
                'action': 'holiday_updated',
                'silent': 'true'
            }
            

            if valid_user_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=valid_user_ids,
                    title=None,
                    body=None,
                    payload={
                        'model': 'resource.calendar.leaves',
                        'record_id': str(self[0].id),  # Use first record's ID for payload
                        'action': 'holiday_updated',
                        'silent': 'true'
                    }
                )

        return res

    def unlink(self):
        company_ids = self.mapped('company_id.id')  # Get unique company IDs

        if company_ids:
            employees = self.env['hr.employee'].search([('company_id', 'in', company_ids)])
            valid_user_ids = employees.mapped('user_id').filtered(lambda u: u.device_token).mapped('id')

            record_ids = self.mapped('id')  # Collect record IDs before deletion

            res = super().unlink()  # Delete records
            payload = {
                'model': 'resource.calendar.leaves',
                'record_id': str(record_ids[0]),  # Use first deleted record's ID
                'action': 'holiday_deleted',
                'silent': 'true'
            }
            _logger.info("Payload (unlink): %s", payload)

            if valid_user_ids and record_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=valid_user_ids,
                    title=None,
                    body=None,
                    payload={
                        'model': 'resource.calendar.leaves',
                        'record_id': str(record_ids[0]),  # Use first deleted record's ID
                        'action': 'holiday_deleted',
                        'silent': 'true'
                    }
                )

            return res


"""Mandatory Days"""

class HrLeaveMandatoryDay(models.Model):
    _inherit = 'hr.leave.mandatory.day'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)

        company_ids = res.mapped('company_id.id')  # Get unique company IDs

        if company_ids:
            employees = self.env['hr.employee'].search([('company_id', 'in', company_ids)])
            valid_user_ids = employees.mapped('user_id').filtered(lambda u: u.device_token).mapped('id')

            if valid_user_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=valid_user_ids,
                    title=None,
                    body=None,
                    payload={
                        'model': 'hr.leave.mandatory.day',
                        'record_id': str(res[0].id),  # Use the first created record ID
                        'action': 'mandatory_leave_added',
                        'silent': 'true'
                    }
                )

        return res

    def write(self, vals):
        """Send notification when a public holiday is updated."""
        res = super().write(vals)

        company_ids = self.mapped('company_id.id')  # Get unique company IDs

        if company_ids:
            employees = self.env['hr.employee'].search([('company_id', 'in', company_ids)])
            valid_user_ids = employees.mapped('user_id').filtered(lambda u: u.device_token).mapped('id')

            if valid_user_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=valid_user_ids,
                    title=None,
                    body=None,
                    payload={
                        'model': 'resource.calendar.leaves',
                        'record_id': str(self[0].id),  # Use first record's ID for payload
                        'action': 'mandatory_day_updated',
                        'silent': 'true'
                    }
                )

        return res

    def unlink(self):
        company_ids = self.mapped('company_id.id')  # Get unique company IDs
        record_ids = self.mapped('id')  # Collect record IDs before deletion

        if company_ids:
            employees = self.env['hr.employee'].search([('company_id', 'in', company_ids)])
            valid_user_ids = employees.mapped('user_id').filtered(lambda u: u.device_token).mapped('id')

            res = super().unlink()  # Delete records

            if valid_user_ids and record_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=valid_user_ids,
                    title=None,
                    body=None,
                    payload={
                        'model': 'hr.leave.mandatory.day',
                        'record_id': str(record_ids[0]),  # Use first deleted record ID
                        'action': 'mandatory_leave_deleted',
                        'silent': 'true'
                    }
                )

            return res



"""Leave type add/delete/update"""

class HrLeaveTypeInherit(models.Model):
    _inherit = 'hr.leave.type'


    @api.model_create_multi
    def create(self, vals_list):
        """Send notification only to users with a registered device_token when a Leave Type is created."""
        res = super().create(vals_list)

        company_ids = res.mapped('company_id.id')  # Get unique company IDs

        if company_ids:
            employees = self.env['hr.employee'].search([('company_id', 'in', company_ids)])
            valid_user_ids = employees.mapped('user_id').filtered(lambda u: u.device_token).mapped('id')

            if valid_user_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=valid_user_ids,
                    title=None,
                    body=None,
                    payload={
                        'model': 'hr.leave.type',
                        'record_id': str(res[0].id),  # Use first record's ID for payload
                        'action': 'leave_type_added',
                        'silent': 'true'
                    }
                )

        return res

    def write(self, vals):
        """Send notification when a Leave Type is updated."""
        res = super().write(vals)

        company_ids = self.mapped('company_id.id')  # Get unique company IDs

        if company_ids:
            employees = self.env['hr.employee'].search([('company_id', 'in', company_ids)])
            valid_user_ids = employees.mapped('user_id').filtered(lambda u: u.device_token).mapped('id')

            if valid_user_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=valid_user_ids,
                    title=None,
                    body=None,
                    payload={
                        'model': 'hr.leave.type',
                        'record_id': str(self[0].id),  # Use first record's ID for payload
                        'action': 'leave_type_updated',
                        'silent': 'true'
                    }
                )

        return res

    def unlink(self):
        """Send notification when a Leave Type is deleted."""
        company_ids = self.mapped('company_id.id')  # Get unique company IDs
        leave_type_ids = self.mapped('id')  # Store IDs before deletion

        if company_ids:
            employees = self.env['hr.employee'].search([('company_id', 'in', company_ids)])
            valid_user_ids = employees.mapped('user_id').filtered(lambda u: u.device_token).mapped('id')

            if valid_user_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=valid_user_ids,
                    title=None,
                    body=None,
                    payload={
                        'model': 'hr.leave.type',
                        'record_id': str(leave_type_ids[0]),  # Use first record's ID for payload
                        'action': 'leave_type_deleted',
                        'silent': 'true'
                    }
                )
                

        return super().unlink()




"""Allocation Update"""

class HrLeaveAllocationInherit(models.Model):
    _inherit = 'hr.leave.allocation'

    def write(self, vals):
        original_states = {record.id: record.state for record in self} if 'state' in vals else {}

        res = super().write(vals)  # Perform the update

        users = self.mapped('employee_id.user_id').filtered(lambda u: u and u.id)
        user_ids = users.ids

        if user_ids:  # If any field is updated
            self.env['mobile.notification.service'].send_fcm_notification(
                user_ids=user_ids,
                title=None,
                body=None,
                payload={
                    'model': 'hr.leave.allocation',
                    'record_id': ','.join(map(str, self.ids)),  # Handle multiple updates
                    'action': 'leave_allocation_updated',
                    'silent': 'true'
                }
            )

        return res



"""Task create/assign/unassign/deleted"""
class ProjectTask(models.Model):
    _inherit = 'project.task'

    @api.model
    def create(self, vals):
        """Send notification when a new task is assigned."""
        task = super().create(vals)

        assigned_users = task.user_ids.filtered(lambda user: user.device_token)
        if assigned_users:
            self.env['mobile.notification.service'].send_fcm_notification(
                user_ids=assigned_users.ids,
                title=None,
                body=None,
                payload={
                    'model': 'project.task',
                    'record_id': str(task.id),
                    'action': 'new_task_created',
                    'silent': 'true'
                }
            )

        return task

    def write(self, vals):
        """Send notifications when users are added or removed from tasks."""
        old_users = self.mapped('user_ids')  # Users before update
        res = super().write(vals)  # Perform update
        new_users = self.mapped('user_ids')  # Users after update

        removed_users = (old_users - new_users).filtered(lambda user: user.device_token)
        added_users = (new_users - old_users).filtered(lambda user: user.device_token)

        if removed_users:
            self.env['mobile.notification.service'].send_fcm_notification(
                user_ids=removed_users.ids,
                title=None,
                body=None,
                payload={
                    'model': 'project.task',
                    'record_id': ','.join(map(str, self.ids)),
                    'action': 'task_unassigned',
                    'silent': 'true'
                }
            )

        if added_users:
            self.env['mobile.notification.service'].send_fcm_notification(
                user_ids=added_users.ids,
                title=None,
                body=None,
                payload={
                    'model': 'project.task',
                    'record_id': ','.join(map(str, self.ids)),
                    'action': 'task_assigned',
                    'silent': 'true'
                }
            )

        return res

    def unlink(self):
        """Send notification before a task is deleted."""
        users_to_notify = self.mapped('user_ids').filtered(lambda user: user.device_token)

        if users_to_notify:
            self.env['mobile.notification.service'].send_fcm_notification(
                user_ids=users_to_notify.ids,
                title=None,
                body=None,
                payload={
                    'model': 'project.task',
                    'record_id': ','.join(map(str, self.ids)),
                    'action': 'task_deletion',
                    'silent': 'true'
                }
            )

        return super().unlink()


""" Create/Delete stage"""

class TodoTaskStage(models.Model):
    _inherit = 'project.task.type'

    @api.model
    def create(self, vals):
        stage=super(TodoTaskStage,self).create(vals)

        users = self.env['res.users'].search([])
        user_ids= [user.id for user in users if user.device_token]

        if user_ids:
            self.env['mobile.notification.service'].send_fcm_notification(
                user_ids=user_ids,
                title=None,
                body=None,
                payload={
                    'model':'project.task.type',
                    'record_id':str(stage.id),
                    'action':'stage_creation',
                    'silent':"true"
                }

            )
        return stage


    def unlink(self):
        for record in self:
            # Fetch all users with a registered device token
            users = self.env['res.users'].search([])
            user_ids = [user.id for user in users if user.device_token]

            if user_ids:  # Ensure there's at least one user to notify
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=user_ids,  # Send to all users with device tokens
                    title=None,
                    body=None,
                    payload={
                        'model': 'project.task.type',
                        'record_id': str(record.id),
                        'action': 'stage_deletion',
                        'silent': "true"
                    }
                )
        return super(TodoTaskStage, self).unlink()


""" Create New/Edit/Delete Activity """

class MailActivity(models.Model):
    _inherit = 'mail.activity'

    @api.model
    def create(self, vals):
        """Send notification when a new scheduled activity is assigned."""
        activity = super(MailActivity, self).create(vals)
        user = activity.user_id
        if user.device_token:
            self.env['mobile.notification.service'].send_fcm_notification(
                user_ids=[user.id],
                title=None,
                body=None,
                payload={
                    'model': 'mail.activity',
                    'record_id': str(activity.id),
                    'action': 'new_activity_scheduled',
                    'silent': "true"
                }
            )
        return activity

    def write(self, vals):
        """Send notification when a scheduled activity is updated or unassigned."""
        for activity in self:
            old_user = activity.user_id  # Store the old user before update

        res = super(MailActivity, self).write(vals)

        for activity in self:
            new_user = activity.user_id  # Get the new user after update

            # Notify the old user if they were unassigned
            if 'user_id' in vals and old_user and old_user != new_user and old_user.device_token:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=[old_user.id],
                    title=None,
                    body=None,
                    payload={
                        'model': 'mail.activity',
                        'record_id': str(activity.id),
                        'action': 'activity_unassigned',
                        'silent': "true"
                    }
                )

            # Notify the new user if the activity was reassigned
            if new_user and new_user.device_token:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=[new_user.id],
                    title=None,
                    body=None,
                    payload={
                        'model': 'mail.activity',
                        'record_id': str(activity.id),
                        'action': 'activity_assigned',
                        'silent': "true"
                    }
                )

        return res


    def unlink(self):
        for activity in self:
            user = activity.user_id
            if user.device_token:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=[user.id],
                    title=None,
                    body=None,
                    payload={
                        'model': 'mail.activity',
                        'record_id': str(activity.id),
                        'action': 'delete_activity_scheduled',
                        'silent': "true"
                    }
                )
        return super(MailActivity, self).unlink()





class SaleTeamMember(models.Model):
    _inherit = 'crm.team.member'

    @api.model
    def create(self, vals_list):
        records = super(SaleTeamMember, self).create(vals_list)
        users = records.filtered(lambda rec: rec.user_id and rec.user_id.device_token)

        if users:
            self.env['mobile.notification.service'].send_fcm_notification(
                user_ids=users.mapped('user_id.id'),
                title=None,
                body=None,
                payload={
                    'model': 'crm.team.member',
                    'record_id': ','.join(map(str, users.ids)),
                    'action': 'salesperson_added',
                    'silent': "true"
                }
            )
        return records

    def write(self, vals):
        result = super(SaleTeamMember, self).write(vals)
        records = self.filtered(lambda rec: 'active' in vals and not vals['active'] and rec.user_id and rec.user_id.device_token)

        if records:
            self.env['mobile.notification.service'].send_fcm_notification(
                user_ids=records.mapped('user_id.id'),
                title=None,
                body=None,
                payload={
                    'model': 'crm.team.member',
                    'record_id': ','.join(map(str, records.ids)),
                    'action': 'salesperson_removed',
                    'silent': "true"
                }
            )
        return result


"""Sale Team Create/Delete"""

class SaleTeam(models.Model):
    _inherit = 'crm.team'

    @api.model
    def create(self, vals_list):
        record = super(SaleTeam, self).create(vals_list)
        users = self.env['res.users'].search([])
        user_ids = [user.id for user in users if user.device_token]

        if user_ids:
            self.env['mobile.notification.service'].send_fcm_notification(
                user_ids=user_ids,
                title=None,
                body=None,
                payload={
                    'model': 'crm.team',
                    'record_id': str(record.id),
                    'action': 'sale_team_creation',
                    'silent': "true"
                }
            )
        return record


    def unlink(self):
        for record in self:
            # Fetch all users with a registered device token
            users = self.env['res.users'].search([])
            user_ids = [user.id for user in users if user.device_token]

            if user_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=user_ids,
                    title=None,
                    body=None,
                    payload={
                        'model': 'crm.team',
                        'record_id':str(record.id),
                        'action': 'sale_team_deletion',
                        'silent': "true"
                    }
                )
        return super(SaleTeam, self).unlink()


"""Customer  Create/Delete"""
from odoo import models, api


class PartnerContact(models.Model):
    _inherit = 'res.partner'

    @api.model
    def create(self, vals_list):
        record = super(PartnerContact, self).create(vals_list)
        users = self.env['res.users'].search([])
        user_ids = [user.id for user in users if user.device_token]

        if user_ids:
            self.env['mobile.notification.service'].send_fcm_notification(
                user_ids=user_ids,
                title=None,
                body=None,
                payload={
                    'model': 'res.partner',
                    'record_id': str(record.id),
                    'action': 'customer_creation',
                    'silent': "true"
                }
            )
        return record


    def unlink(self):
        for record in self:
            # Fetch all users with a registered device token
            users = self.env['res.users'].search([])
            user_ids = [user.id for user in users if user.device_token]

            if user_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=user_ids,
                    title=None,
                    body=None,
                    payload={
                        'model': 'res.partner',
                        'record_id':str(record.id),
                        'action': 'customer_deletion',
                        'silent': "true"
                    }
                )

        return super(PartnerContact, self).unlink()







