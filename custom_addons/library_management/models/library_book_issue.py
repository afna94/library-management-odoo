# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import date


class LibraryBookIssue(models.Model):
    _name = 'library.book.issue'
    _description = 'Library Book Issue'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'issue_date desc, id desc'

    name = fields.Char(
        string='Reference',
        readonly=True,
        default=lambda self: 'New',
        copy=False,
        tracking=True,
    )
    book_id = fields.Many2one(
        'product.product',
        string='Book',
        required=True,
        tracking=True,
    )
    member_id = fields.Many2one(
        'res.partner',
        string='Member',
        required=True,
        tracking=True,
    )
    issue_date = fields.Date(
        string='Issue Date',
        default=fields.Date.today,
        required=True,
        tracking=True,
    )
    due_date = fields.Date(
        string='Due Date',
        required=True,
        tracking=True,
    )
    return_date = fields.Date(
        string='Return Date',
        readonly=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('issued', 'Issued'),
            ('returned', 'Returned'),
            ('overdue', 'Overdue'),
        ],
        default='draft',
        string='Status',
        tracking=True,
        readonly=True,
    )
    is_overdue = fields.Boolean(
        string='Overdue',
        compute='_compute_is_overdue',
        store=True,
    )
    days_overdue = fields.Integer(
        string='Days Overdue',
        compute='_compute_is_overdue',
        store=True,
    )
    available_qty = fields.Float(
        string='Available Copies',
        related='book_id.qty_available',
        readonly=True,
    )
    fine_rate = fields.Float(
        string='Fine per Day (Rs.)',
        default=2.0,
    )
    fine_amount = fields.Float(
        string='Fine Amount (Rs.)',
        compute='_compute_fine_amount',
        store=True,
    )
    fine_paid = fields.Boolean(
        string='Fine Paid',
        default=False,
        tracking=True,
    )
    notes = fields.Text(string='Notes')

    @api.depends('due_date', 'state', 'return_date')
    def _compute_is_overdue(self):
        today = fields.Date.today()
        for rec in self:
            if rec.state == 'issued' and rec.due_date and rec.due_date < today:
                rec.is_overdue = True
                rec.days_overdue = (today - rec.due_date).days
            else:
                rec.is_overdue = False
                rec.days_overdue = 0

    @api.depends('days_overdue', 'fine_rate', 'state', 'fine_paid')
    def _compute_fine_amount(self):
        for rec in self:
            if rec.days_overdue > 0 and not rec.fine_paid:
                rec.fine_amount = rec.days_overdue * rec.fine_rate
            else:
                rec.fine_amount = 0.0

    @api.constrains('issue_date', 'due_date')
    def _check_dates(self):
        for rec in self:
            if rec.due_date and rec.issue_date:
                if rec.due_date <= rec.issue_date:
                    raise ValidationError(
                        'Due date must be after the issue date.'
                    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'library.book.issue'
                ) or 'New'
        return super().create(vals_list)

    def action_issue(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError('Only draft records can be issued.')
            if rec.book_id.qty_available <= 0:
                raise ValidationError(
                    f'Book "{rec.book_id.name}" has no copies available!'
                )
            rec._update_stock(-1)
            rec.state = 'issued'

    def action_return(self):
        for rec in self:
            if rec.state not in ('issued', 'overdue'):
                raise UserError('Only issued or overdue books can be returned.')
            if rec.fine_amount > 0 and not rec.fine_paid:
                raise UserError(
                    f'Please collect the fine of Rs. {rec.fine_amount:.2f} '
                    f'({rec.days_overdue} days) before returning the book.'
                )
            rec._update_stock(1)
            rec.return_date = fields.Date.today()
            rec.state = 'returned'
            rec.is_overdue = False

    def action_mark_fine_paid(self):
        for rec in self:
            if rec.fine_amount <= 0:
                raise UserError('No fine is pending for this record.')
            rec.fine_paid = True

    def action_set_draft(self):
        self.write({'state': 'draft', 'fine_paid': False})

    def _update_stock(self, qty_change):
        # ഏത് internal location-ലും stock ഉണ്ടെങ്കിൽ അവിടെ നിന്ന് automatically എടുക്കും
        quant = self.env['stock.quant'].search([
            ('product_id', '=', self.book_id.id),
            ('location_id.usage', '=', 'internal'),
            ('quantity', '>', 0),
        ], order='quantity desc', limit=1)

        if quant:
            # Stock ഉള്ള location use ചെയ്യും
            location = quant.location_id
        else:
            # Stock ഇല്ലെങ്കിൽ default WH/Stock
            location = self.env.ref('stock.stock_location_stock')

        # ആ location-ൽ quant ഉണ്ടോ എന്ന് check ചെയ്യും
        existing = self.env['stock.quant'].search([
            ('product_id', '=', self.book_id.id),
            ('location_id', '=', location.id),
        ], limit=1)

        if existing:
            existing.sudo().write({
                'quantity': existing.quantity + qty_change
            })
        else:
            self.env['stock.quant'].sudo().create({
                'product_id': self.book_id.id,
                'location_id': location.id,
                'quantity': qty_change,
            })

    def action_check_overdue(self):
        today = fields.Date.today()
        overdue_issues = self.search([
            ('state', '=', 'issued'),
            ('due_date', '<', today),
        ])
        if overdue_issues:
            overdue_issues.write({'state': 'overdue'})
            template = self.env.ref(
                'library_management.email_template_overdue_book',
                raise_if_not_found=False,
            )
            if template:
                for issue in overdue_issues:
                    template.send_mail(issue.id, force_send=True)