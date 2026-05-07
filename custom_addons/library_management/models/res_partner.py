# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    book_issue_ids = fields.One2many(
        'library.book.issue',
        'member_id',
        string='Borrowing History',
    )
    borrow_count = fields.Integer(
        string='Total Borrows',
        compute='_compute_borrow_count',
    )
    active_borrow_count = fields.Integer(
        string='Currently Borrowed',
        compute='_compute_borrow_count',
    )
    overdue_count = fields.Integer(
        string='Overdue Books',
        compute='_compute_borrow_count',
    )

    @api.depends('book_issue_ids', 'book_issue_ids.state')
    def _compute_borrow_count(self):
        for partner in self:
            issues = partner.book_issue_ids
            partner.borrow_count = len(issues)
            partner.active_borrow_count = len(
                issues.filtered(lambda i: i.state in ('issued', 'overdue'))
            )
            partner.overdue_count = len(
                issues.filtered(lambda i: i.state == 'overdue')
            )

    def action_view_borrows(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Borrowing History',
            'res_model': 'library.book.issue',
            'view_mode': 'list,form',
            'domain': [('member_id', '=', self.id)],
            'context': {'default_member_id': self.id},
        }
