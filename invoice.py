#!/usr/bin/env python
#
# Copyright 2012 by Jeffrey M. Laughlin <jeff.laughlin@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging

from optparse import OptionParser
import os
import os.path
import sys
import webbrowser

from mako.template import Template
from mako import exceptions

import gnucash
from gnucash import gnucash_business


class Entry(object):
    @staticmethod
    def from_gnc_entry(gnc_entry):
        gnc_entry = gnucash_business.Entry(instance=gnc_entry)
        entry = Entry()
        entry.date=gnc_entry.GetDate()
        entry.desc=gnc_entry.GetDescription()
        entry.units="Hours"
        entry.qty=gnucash.GncNumeric(instance=gnc_entry.GetQuantity()).to_double()
        entry.unit_cost=gnucash.GncNumeric(instance=gnc_entry.GetInvPrice()).to_double()
        return entry


class Customer(object):
    @staticmethod
    def from_gnc_customer(gnc_customer):
        customer = Customer()
        customer.name = gnc_customer.GetName()
        customer.contact = gnc_customer.GetAddr().GetName()
        customer.email = gnc_customer.GetAddr().GetEmail()
        customer.phone = gnc_customer.GetAddr().GetPhone()
        addr = [
            gnc_customer.GetAddr().GetAddr1(),
            gnc_customer.GetAddr().GetAddr2(),
            gnc_customer.GetAddr().GetAddr3(),
            gnc_customer.GetAddr().GetAddr4(),
        ]
        customer.address = [a for a in addr if a != ""]
        return customer


class Vendor(object):
    pass


class Invoice(object):
    @staticmethod
    def from_gnc_invoice(gnc_inv):
        invoice = Invoice()
        job = gnc_inv.GetOwner()
        customer = job.GetOwner()
        invoice.number = gnc_inv.GetID()
        invoice.date_opened = gnc_inv.GetDateOpened()
        invoice.date_posted = gnc_inv.GetDatePosted()
        invoice.date_due = gnc_inv.GetDateDue()
        invoice.customer = Customer.from_gnc_customer(customer)
        vendor = Vendor()
        vendor.name = "Jeff Laughlin Consulting"
        vendor.contact = "Jeff Laughlin"
        vendor.email = "jeff.laughlin@gmail.com"
        vendor.phone = "858-232-2005"
        vendor.address = ["8 Edgewood Ave", "Barre, VT 05641"]
        invoice.vendor = vendor
        invoice.entries = []
        for gnc_entry in gnc_inv.GetEntries():
            entry = Entry.from_gnc_entry(gnc_entry)
            invoice.entries.append(entry)
        return invoice

usage='%(prog)s [options] gnucash_book_url invoice_id_1 [invoice_id_2] ... [invoice_id_x]'

def main(argv=None):
    if argv is None:
        argv = sys.argv

    op = OptionParser(usage=usage)
    opts, args = op.parse_args(argv[1:])

    #input_url="file:///home/jeff/consulting/gnucash/jefflaughlinconsultingllc.gnucash"
    try:
        input_url, invoice_ids = args[0], args[1:]
    except Exception:
        # print usage
        logging.critical("Must supply book URL and at least one invoice ID.")
        op.print_help()
        return 1
    session = gnucash.Session(input_url,ignore_lock=True)
    book = session.book
    root_account = book.get_root_account()
    #i = book.InvoiceLookupByID("000002")
    out_files = []
    for invoice_id in invoice_ids:
        i = book.InvoiceLookupByID(invoice_id)
        invoice = Invoice.from_gnc_invoice(i)
        t = Template(filename='templates/invoice.html')
        out_path = 'invoice_%s.html' % invoice_id
        out_files.append(out_path)
        try:
            with open(out_path, 'w') as f:
                f.write(
                    t.render(invoice=invoice)
                )
        except Exception:
            print exceptions.text_error_template().render()
            raise
        else:
            webbrowser.open("file://" + os.path.join(os.path.abspath(os.curdir), out_path))


if __name__ == '__main__':
    sys.exit(main())

