# -*- coding: utf-8 -*-


from odoo import http
from odoo.http import request
import base64
import face_recognition
import io  # Import BytesIO
import logging

_logger = logging.getLogger(__name__)


class FaceRecognitionController(http.Controller):
    @http.route('/hr_attendance/verify_employee_face', type='json', auth='user')
    def verify_employee_face(self, employee_id, image_data, checkout=False):
        employee = request.env['hr.employee'].browse(int(employee_id))
        if not employee.image_1920:
            return {'matched': False, 'error': 'No image found for employee'}

        # Decode stored image
        stored_image_data = base64.b64decode(employee.image_1920)
        stored_image_file = io.BytesIO(stored_image_data)
        stored_image = face_recognition.load_image_file(stored_image_file)

        # Decode captured image
        captured_image_data = base64.b64decode(image_data)
        captured_image_file = io.BytesIO(captured_image_data)
        captured_image = face_recognition.load_image_file(captured_image_file)

        # Get encodings
        stored_encoding = face_recognition.face_encodings(stored_image)
        captured_encoding = face_recognition.face_encodings(captured_image)

        if not stored_encoding or not captured_encoding:
            return {'matched': False, 'error': 'No face detected in image'}

        # Compare faces
        match = face_recognition.compare_faces([stored_encoding[0]], captured_encoding[0])
        if match[0]:
            _logger.info("I am hereeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee")
            attendance = request.env['hr.attendance'].sudo().search([
                ('employee_id', '=', employee.id),
            ], order='check_in desc', limit=1)
            _logger.info("Created Atendndndnndndndddddddddddddddddddddddddddddddddddddddddddddddd")
            _logger.info("Created Ateendddddddd %s", attendance)
            if attendance:
                _logger.info("Inside Oneeeeeeeeeeeeeeeeeeeeeeeeeeeeee")

                # Update the attendance record with the captured image
                if checkout:
                    _logger.info("Inside Twooooooooooooooooooooooooooo")
                    attendance.sudo().write({'checkout_image': image_data})
                    _logger.info("Inside Threeeeeeeeeeeeeeeeeeeeeeeeeeeeee")
            return {'matched': True}
        return {'matched': False}

    @http.route('/get_checkin_image', type='json', auth='user')
    def _save_checkin_image(self, employee_id, image_data, checkout=False):
        attendance = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee_id),
        ], order='check_in desc', limit=1)
        _logger.info("Inside the save checking image method Ateendddddddd %s", attendance)
        if attendance and not checkout:
            attendance.sudo().write({'checkin_image': image_data})


    @http.route('/hr_attendance/systray_check_in_out', type='json', auth='user')
    def systray_check_in_out(self, checkout=False):
        # Handle the logic for both check-in and check-out,
        # 'checkout' will determine if it's check-out
        employee = request.env.user.employee_id
        _logger.info("Inside employee %s", employee)

        if checkout:
            _logger.info("Inside checkoute %s", checkout)

            # Mark the employee as checked-out
            employee.attendance_state = 'checked_out'
        else:
            # Mark the employee as checked-in
            employee.attendance_state = 'checked_in'

        return {'status': 'success'}

    @http.route('/attendance/face_recognition_setting', type='json', auth='user')
    def get_face_recognition_setting(self):
        """ Securely fetch face recognition setting """
        value = request.env["ir.config_parameter"].sudo().get_param("ps_attendance_face_recognition.is_face_recognition")
        return {"is_face_recognition": value == "True"}

