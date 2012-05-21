import pymongo
import random
from datetime import datetime, timedelta
from helpers import gen_id, get_next_renewal_date
from mongoengine import *
from models import *

connect('revrec')

def seed_db(db):
    """
    Seed Mongo database with fake data
    """
    clear_collections(db)
    for i in range(1, 2):
        gen_invoice()

def clear_collections(db):
    """
    Clear Mongo collections.
    """
    db['invoice'].remove()
    db['invoice_item'].remove()
    db['payment'].remove()
    db['refund'].remove()
    db['term_extension'].remove()
    db['monthly_entry'].remove()

def gen_invoice():
    """
    Generate a fake invoice
    """
    invoice_id = gen_id()
    account_id = gen_id()
    invoice_date = datetime(2012, random.choice(range(1,13)), random.choice(range(1,29)))

    invoice_item_amounts = [gen_invoice_item(account_id, invoice_id, invoice_date)]
    invoice_amount = sum([i['total_amount'] for i in invoice_item_amounts])

    # Create invoice
    invoice = Invoice(invoice_id=invoice_id,
                      account_id=account_id,
                      invoice_date=invoice_date,
                      invoice_amount=invoice_amount)
    invoice.save()

    # Create payment
    payment_id = None
    if roll_dice(1):
        payment_results = gen_payment(account_id=account_id, 
                                      invoice_id=invoice_id,  
                                      invoice_date=invoice_date, 
                                      amount=invoice_amount)
        payment_id = payment_results[0]
        payment_date = payment_results[1]

    # Create refund
    if roll_dice(0) and payment_id is not None:
        refund = gen_refund(account_id=account_id, 
                            invoice_id=invoice_id, 
                            invoice_date=invoice_date, 
                            amount=invoice_amount, 
                            payment_id=payment_id,
                            payment_date=payment_date)

    # Create term extension
    if roll_dice(0) and payment is not None:
        ext = gen_term_extension(account_id=account_id, 
                                 invoice_id=invoice_id, 
                                 invoice_date=invoice_date,
                                 service_start=invoice_items[0].service_start,
                                 service_end=invoice_items[0].service_end)

def gen_invoice_item(account_id, invoice_id, invoice_date):
    """
    Generate a fake invoice item
    """
    plans = ['Unlimited', 'Standard']
    billperiods = ['Monthly']
    billperiod_months = {'Monthly': 1, 'Yearly': 12, 'Biyearly':24}
    amounts = {
        'Unlimited': {'Monthly': 20, 'Yearly': 220, 'Biyearly': 400}, 
        'Standard': {'Monthly': 10, 'Yearly': 110, 'Biyearly': 200}
    }

    item_id = gen_id()
    plan = random.choice(plans)
    billperiod = random.choice(billperiods)
    amount = amounts[plan][billperiod]

    item = InvoiceItem(
        item_id=item_id,
        invoice_id=invoice_id,
        account_id=account_id, 
        charge_date=invoice_date,
        plan=plan,
        billperiod=billperiod,
        item_amount=amount, 
        tax_amount=0,
        total_amount=amount,
        service_start=invoice_date,
        service_end=get_next_renewal_date(invoice_date, invoice_date, 
                          billperiod_months[billperiod]) - timedelta(1)
    )

    item.save()
    print 'Created invoice item.'

    return {'total_amount': amount}

def gen_payment(account_id, invoice_id, invoice_date, amount):
    """Generate a fake payment
    """
    if roll_dice(0):
        paid_days_late = 0
    else:
        paid_days_late = random.choice(range(1,16))

    payment_id = gen_id()
    payment_date = invoice_date + timedelta(paid_days_late)
    payment = Payment(
        payment_id=payment_id,
        account_id=account_id,
        invoice_id=invoice_id,
        payment_date=payment_date,
        amount=amount
    )
    payment.save()
    return [payment_id, payment_date]

def gen_refund(account_id, invoice_id, invoice_date, amount, payment_id, payment_date):
    """Generate a fake refund
    """
    refund = Refund(
        refund_id=gen_id(),
        account_id=account_id,
        invoice_id=invoice_id,
        payment_id=payment_id,
        refund_amount=amount * random.choice(range(10, 101))/100,
        refund_date=payment_date + timedelta(random.choice(range(1,29 - (payment_date - invoice_date).days))),
        cancel_flag=random.choice([True,False])
    )
    refund.save()

def gen_term_extension(account_id, invoice_id, invoice_date, service_start, service_end):
    """Generate a fake term extension
    """
    ext = TermExtension(
        term_extension_id=gen_id(),
        account_id=account_id,
        invoice_id=invoice_id,
        grant_date=grant_date + timedelta(random.choice(range(1,29))),
        service_start=service_start,
        service_end=service_end
    )
    ext.save()

def roll_dice(prob):
    return random.choice(range(1, 101)) < 100 * prob