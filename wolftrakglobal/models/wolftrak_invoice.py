# -*- coding: utf-8 -*-
import json
import sys, os
from odoo import api, fields, models, _
from bs4 import BeautifulSoup
import requests

main_base = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE_NAME = 'ncf.json'
CONFIG_FILE = os.path.join(main_base, CONFIG_FILE_NAME)

def load_config(json_file):
    with open(json_file, 'r') as file:
        config_data = json.load(file)
        return config_data

def get_ncf_record(ncf,rnc, config_data = None):
    if not config_data:
        config_data = load_config(CONFIG_FILE)
    req_headers = config_data['request_headers']
    # req_cookies = config_data['request_cookies']
    req_params = config_data['request_parameters']
    uri = ''.join([config_data['url'], config_data['web_resource']])
    req_params['txtNCF'] = ncf
    req_params['txtRNC'] = rnc
    result = requests.get(uri, params = req_params, headers = req_headers)
    if result.status_code == requests.codes.ok:
        soup = BeautifulSoup(result.content)
        if soup.find('span', attrs={'id': 'lblContribuyente'}):
            data_rows1 = soup.find('span', attrs={'id': 'lblContribuyente'})
            data_rows2 = soup.find('span', attrs={'id': 'lblTipoComprobante'})
            span = []
            span.append(data_rows1.string)
            span.append(data_rows2.string)
            return span
        else:
            print soup.find('span', attrs={'id': 'lblErrorWebService'}).string

class WolftrakInvoice(models.Model):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    def default_ex_rate(self):
        page = requests.get('http://promerica.com.do/?d=1014')
        soup = BeautifulSoup(page.content, 'lxml')
        form = soup.body
        result = form.find_all(href='http://www.promerica.com.do/?p=1014')
        link = result[0]
        str_final = link.string
        venta = str_final[str_final.find('V'):].encode('utf-8')
        rate = float(venta[venta.find('$')+1:venta.find('$')+6])
        user = self.env.user
        if user.company_id.name == 'Mytraktech':
            return rate
        else:
            return 0.0

    ncf = fields.Char(string="Número de Comprobante Fiscal")

    type_comp = fields.Char(string="Tipo de Comprobante", readonly=True, compute='ncf_validation')

    ncf_result = fields.Char(string="Resultado", readonly=True, compute='ncf_validation')

    tax_hold = fields.Monetary(string="ITBIS Retenido")

    type_ci = fields.Char(string="Tipo de Identificación")

    isr = fields.Selection([('0.3','30%'),
                            ('0.27','27%')], string="Impuesto Sobre la Renta")

    isr_hold = fields.Float(string="Total retenido")

    isr_date = fields.Date(string="Fecha de la Retencion")

    type_buy = fields.Selection([('01','01 - Gastos de personal'),
                                ('02','02 - Gastos por trabajos suministros y servicios'),
                                ('03','03 - Arrendamientos'),
                                ('04','04 - Gastos de activos fijo'),
                                ('05','05 - Gastos de representación'),
                                ('06','06 - Otras deducciones admitisdas'),
                                ('07','07 - Gastos financieros'),
                                ('08','08 - Gastos Extraordinarios'),
                                ('09','09 - Compras y Gastos que formarann parte del costo de venta'),
                                ('10','10 - Adquisiciones de activos'),
                                ('11','11 - Gastos de Seguros')], string="Tipo de Bienes o Servicios comprados")

    type_nul = fields.Selection([('01','01 Deterioro de Factura Pre-Imresa'),
                                ('02','02 Errores de Impresión (factura Pre-Impresa)'),
                                ('03','03 Impresión Defectuosa'),
                                ('04','04 Duplicidad de Factura'),
                                ('05','05 Correción de la Información'),
                                ('06','06 Cambio de Productos'),
                                ('07','07 Devolución de Productos'),
                                ('08','08 Omisión de Productos'),
                                ('09','09 Errores de Secuencias de NCF')], string="Tipo de Anulación")

    ex_rate = fields.Float(string='Tasa de Cambio', digits=(1,4),default=default_ex_rate)

    @api.onchange('isr')
    def isr_holding(self):
        self.isr_hold = self.amount_total * float(self.isr)

    @api.onchange('amount_tax')
    def tax_holding(self):
        p_id = self.partner_id.id
        partner = self.env['res.partner'].search([('id', '=', p_id)])
        rnc = partner.doc_ident
        if type(rnc) != bool:
            if len(rnc) == 11:
                # Es una persona natural
                self.tax_hold += self.amount_tax*1.0
                self.type_ci = 2
            else:
                self.tax_hold += 0.0
                self.type_ci = 1

    @api.depends('ncf')
    def ncf_validation(self):
        supplier_rnc = self.env['res.partner'].search([('id', '=', self.partner_id.id)])
        values = get_ncf_record(self.ncf,supplier_rnc.doc_ident)
        if values != None:
            self.type_comp = values[1]
            self.ncf_result = "El Número de Comprobante Fiscal digitado es válido."
        else:
            self.ncf_result = "El Número de Comprobante Fiscal ingresado no es correcto o no corresponde a este RNC"