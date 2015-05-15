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

import ctypes
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

log = logging.getLogger(__name__)

# gnucash-python doesn't have the functions we need to get the company info
# from the book. This ugly hack gets the job done.
libgnc_qof = ctypes.CDLL('/usr/lib/x86_64-linux-gnu/gnucash/libgnc-qof.so')
libgnc_qof.kvp_value_get_string.restype = ctypes.c_char_p
libgnc_qof.kvp_frame_get_slot_path.restype = ctypes.c_void_p
libgnc_qof.qof_book_get_slots.restype = ctypes.c_void_p

class BusinessSlots(object):
    def __init__(self, book):
        self._slots = libgnc_qof.qof_book_get_slots(ctypes.c_void_p(book.instance.__long__()))
    def __getitem__(self, key):
        kvpv = libgnc_qof.kvp_frame_get_slot_path(
                        self._slots, 'options', 'Business', key, None)
        val = libgnc_qof.kvp_value_get_string(kvpv)
        return val

class Entry(object):
    @staticmethod
    def from_gnc_entry(gnc_entry):
        entry = Entry()
        entry.date=gnc_entry.GetDate()
        entry.desc=gnc_entry.GetDescription()
        entry.units=gnc_entry.GetAction()
        entry.qty=gnc_entry.GetQuantity().to_double()
        entry.unit_cost=gnc_entry.GetInvPrice().to_double()
        return entry


class Customer(object):
    def __init__(self):
        self.name = None
        self.contact = None
        self.email = None
        self.phone = None
        self.addr = []

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


class Job(object):
    def __init__(self):
        self.name = None
        self.reference = None

    @staticmethod
    def from_gnc_job(gnc_job):
        job = Job()
        job.name = gnc_job.GetName()
        job.reference = gnc_job.GetReference()
        return job


class UnknownOwnerType(Exception): pass


class Invoice(object):
    def __init__(self):
        self.job = Job()
        self.customer = Customer()

    @staticmethod
    def from_gnc_invoice(gnc_inv, slots):
        invoice = Invoice()
        # This returns a `Customer` object when Job is None
        owner = gnc_inv.GetOwner()
        if owner is not None:
            if isinstance(owner, gnucash_business.Customer):
                invoice.customer = Customer.from_gnc_customer(owner)
            elif isinstance(owner, gnucash_business.Job):
                invoice.job = Job.from_gnc_job(owner)
                customer = owner.GetOwner()
                invoice.customer = Customer.from_gnc_customer(customer)
            else:
                raise UnknownOwnerType(type(owner))
        invoice.number = gnc_inv.GetID()
        invoice.date_opened = gnc_inv.GetDateOpened()
        invoice.date_posted = gnc_inv.GetDatePosted()
        invoice.date_due = gnc_inv.GetDateDue()
        invoice.billing_id = gnc_inv.GetBillingID()
        # NOTE This should probably be "Company" and not "Vendor"
        vendor = Vendor()
        # NOTE These may need to support internationalization
        vendor.employer_id = slots['Company ID']
        vendor.name = slots['Company Name']
        vendor.contact = slots['Company Contact Person']
        vendor.email = slots['Company Email Address']
        vendor.phone = slots['Company Phone Number']
        addr = slots['Company Address']
        vendor.address = addr.split('\n') if addr is not None else []
        vendor.website = slots['Company Website URL']
        invoice.vendor = vendor
        invoice.entries = []
        for gnc_entry in gnc_inv.GetEntries():
            entry = Entry.from_gnc_entry(gnc_entry)
            invoice.entries.append(entry)
        return invoice

usage='%(prog)s [options] gnucash_book_url invoice_id_1 [invoice_id_2] ... [invoice_id_x]'

def main(argv=None):
    logging.basicConfig(level=logging.DEBUG)

    if argv is None:
        argv = sys.argv

    op = OptionParser(usage=usage)
    opts, args = op.parse_args(argv[1:])

    #input_url="file:///home/jeff/consulting/gnucash/jefflaughlinconsultingllc.gnucash"
    try:
        input_url, invoice_ids = args[0], args[1:]
    except Exception:
        # print usage
        log.critical("Must supply book URL and at least one invoice ID.")
        op.print_help()
        return 1
    session = gnucash.Session(input_url,ignore_lock=True)
    book = session.book
    root_account = book.get_root_account()
    slots = BusinessSlots(book)
    #i = book.InvoiceLookupByID("000002")
    out_files = []
    for invoice_id in invoice_ids:
        i = book.InvoiceLookupByID(invoice_id)
        if i is None:
            log.error("Failed to lookup invoice '%s'" % invoice_id)
            continue
        invoice = Invoice.from_gnc_invoice(i, slots)
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

