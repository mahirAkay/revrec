from mongoengine import *
from helpers import pretty_date

class MonthlyEntry(Document):
    account_id = StringField()
    year = IntField()
    month = IntField()
    cr_rev = FloatField()
    ending_defrev = FloatField()
    cumul_rev = FloatField()
    cr_ref_payable = FloatField()
    dr_reserve_ref = FloatField()
    dr_contra_rev = FloatField()
    dr_defrev = FloatField()
    dr_reserve_graceperiod = FloatField()
    cr_contra_rev = FloatField()
    meta = {
        'indexes': ['year', 'month']
    }

class Invoice(Document):
    """
    An invoice.
    """
    account_id = StringField()
    invoice_id = StringField()
    invoice_date = DateTimeField()
    invoice_amount = FloatField()
    meta = {
        'indexes': ['invoice_id', 'invoice_date']
    }

    def is_paid(self):
        """
        Returns true if total invoice amount equals total payment amount.
        """
        payment = Payment.objects(invoice_id=self.invoice_id).first()

        if payment and payment.amount == self.invoice_amount:
            return True 
        else:
            return False

class InvoiceItem(Document):
    """
    An invoice item. Multiple invoice items can exist on a single invoice.
    """
    item_id = StringField()
    account_id = StringField()
    invoice_id = StringField()
    charge_date = DateTimeField()
    charge_name = StringField()
    item_amount = FloatField()
    tax_amount = FloatField()
    total_amount = FloatField()
    service_start = DateTimeField()
    service_end = DateTimeField()
    plan = StringField()
    billperiod = StringField()
    acct_code = StringField()
    meta = {
        'indexes': ['invoice_id']
    }

class Payment(Document):
    """
    A payment. Must be related to an invoice.
    """
    payment_id = StringField()
    invoice_id = StringField()
    payment_date = DateTimeField()
    amount = FloatField()
    meta = {
        'indexes': ['invoice_id', 'payment_date']
    }

class Refund(Document):
    """
    A refund.
    """
    refund_id = StringField()
    invoice_id = StringField()
    payment_id = StringField()
    refund_date = DateTimeField()
    refund_amount = FloatField()
    cancel_flag = BooleanField()
    meta = {
       'indexes': ['invoice_id', 'refund_date']
    }

class TermExtension(Document):
    """
    A term extension.
    """
    term_extension_id = StringField()
    invoice_id = StringField()
    grant_date = DateTimeField()
    service_start = DateTimeField()
    service_end = DateTimeField()
    meta = {
        'indexes': ['invoice_id', 'grant_date']
    }
