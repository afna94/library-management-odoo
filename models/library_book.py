# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class LibraryBook(models.Model):
    _inherit = 'product.template'

    is_library_book = fields.Boolean(
        string='Is Library Book',
        default=False,
        help='Check this to mark product as a library book.',
    )
    author = fields.Char(string='Author', tracking=True)
    isbn = fields.Char(string='ISBN', size=20, tracking=True)
    book_category = fields.Selection([
        ('fiction', 'Fiction'),
        ('non_fiction', 'Non-Fiction'),
        ('reference', 'Reference'),
        ('textbook', 'Textbook'),
        ('magazine', 'Magazine'),
        ('other', 'Other'),
    ], string='Book Category', tracking=True)
    publisher = fields.Char(string='Publisher')
    publication_year = fields.Integer(string='Publication Year')
    edition = fields.Char(string='Edition')
    language = fields.Selection([
        ('english', 'English'),
        ('malayalam', 'Malayalam'),
        ('hindi', 'Hindi'),
        ('other', 'Other'),
    ], string='Language', default='english')
    total_copies = fields.Integer(string='Total Copies', default=1)
    borrowed_copies = fields.Integer(
        string='Borrowed Copies',
        compute='_compute_borrowed_copies',
        store=True,
    )
    available_copies = fields.Integer(
        string='Available Copies',
        compute='_compute_borrowed_copies',
        store=True,
    )

    @api.depends('total_copies')
    def _compute_borrowed_copies(self):
        for book in self:
            issued = self.env['library.book.issue'].search_count([
                ('book_id.product_tmpl_id', '=', book.id),
                ('state', 'in', ['issued', 'overdue']),
            ])
            book.borrowed_copies = issued
            book.available_copies = book.total_copies - issued

    @api.constrains('isbn')
    def _check_isbn(self):
        for rec in self:
            if rec.isbn:
                existing = self.search([
                    ('isbn', '=', rec.isbn),
                    ('id', '!=', rec.id),
                ])
                if existing:
                    raise ValidationError(
                        f'ISBN "{rec.isbn}" already exists for '
                        f'book "{existing[0].name}"!'
                    )

    @api.constrains('total_copies')
    def _check_total_copies(self):
        for rec in self:
            if rec.total_copies < 0:
                raise ValidationError(
                    'Total copies cannot be negative!'
                )

    def action_view_issues(self):
        return {
            'type': 'ir.actions.act_window',
            'name': f'Issues — {self.name}',
            'res_model': 'library.book.issue',
            'view_mode': 'list,form',
            'domain': [('book_id.product_tmpl_id', '=', self.id)],
            'context': {'default_book_id': self.product_variant_ids[:1].id},
        }