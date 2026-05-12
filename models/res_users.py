# -*- coding: utf-8 -*-
from odoo import models, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._sync_customer_only_group()
        return users

    def write(self, vals):
        res = super().write(vals)
        if 'groups_id' in vals:
            self._sync_customer_only_group()
        return res

    def _sync_customer_only_group(self):
        customer_group = self.env.ref(
            'library_management.group_library_customer', raise_if_not_found=False)
        customer_only_group = self.env.ref(
            'library_management.group_library_customer_only', raise_if_not_found=False)
        reception_group = self.env.ref(
            'library_management.group_library_reception', raise_if_not_found=False)

        if not (customer_group and customer_only_group and reception_group):
            return

        for user in self:
            is_customer = customer_group in user.groups_id
            is_reception_or_above = reception_group in user.groups_id

            if is_customer and not is_reception_or_above:
                if customer_only_group not in user.groups_id:
                    user.sudo().write({'groups_id': [(4, customer_only_group.id)]})
            else:
                if customer_only_group in user.groups_id:
                    user.sudo().write({'groups_id': [(3, customer_only_group.id)]})