from __future__ import division
from calendar import monthrange
from datetime import datetime, timedelta, date
from helpers import pretty_date, last_day_of_month
from seed import seed_db
from mongoengine import connect
from models import *
from use_cases import *
import pprint
import pymongo

GRACE_PERIOD = 16
invoices = {}

"""
-------------------
REVENUE RECOGNITION
-------------------
"""
def recognize_revenue(obs_date=datetime(2014,1,1)):
    """Cycles through invoices in the MongoDB invoice collection and performs
    revenue recognition on each in turn. Results will be persisted in the db.

    :param obs_date: Reporting date. Events that occur after this date should
                     be excluded from the revenue recognition process.
    """

    invoices = Invoice.objects(invoice_date__lte=obs_date)
    print '%s invoices found.' % len(invoices)

    for invoice in invoices:
        process_invoice(invoice, obs_date)

def process_invoice(invoice, return_dict=False, obs_date=datetime(2014,1,1)):
    """For a specified invoice, loops through the invoice items and creates
    a daily revenue recognition schedule for each in turn and persists the
    schedule as a monthly rollup into MongoDB.

    :param invoice: Invoice object.
    :param return_dict: True if returns dictionary for template use.
    :param obs_date: Reporting date. Events that occur after this date should
                     be excluded from the revenue recognition process.
    :return dict. If :param return_dict is True, returns dictionary for template use.
    """
    # Retrieve objects relevant to this invoice
    invoice_items = InvoiceItem.objects(invoice_id=invoice.invoice_id)
    payment = Payment.objects(invoice_id=invoice.invoice_id, payment_date__lte=obs_date).first()
    refunds = Refund.objects(invoice_id=invoice.invoice_id, refund_date__lte=obs_date)
    term_extensions = TermExtension.objects(invoice_id=invoice.invoice_id, grant_date__lte=obs_date)

    print 'Counts: invitems: %s, pmt: %s, refs: %s, termexts: %s' % (len(invoice_items),
                                                                     payment,
                                                                     len(refunds),
                                                                     len(term_extensions))

    # If invoice is paid, create the revenue recognition schedule
    if invoice.is_paid():

        # Recognize revenue on each invoice item
        for item in invoice_items:

            # Generate base amortization schedule based on amount, service term, payment date.
            revrec_schedule = amortize_service_fee(item=item, payment_date=payment.payment_date)

            # Adjust the schedule in the case of a late payment, i.e. when the grace period is used.
            gp_notes = apply_grace_period(revrec_schedule=revrec_schedule,
                                          item=item,
                                          payment_date=payment.payment_date)

            # Adjust the schedule for term extensions
            apply_term_extensions(revrec_schedule=revrec_schedule, 
                                  item=item, 
                                  term_extensions=term_extensions)

            # Adjust the schedule for refunds
            apply_refunds(revrec_schedule=revrec_schedule, 
                          invoice_amount=invoice.invoice_amount,
                          item=item, 
                          refunds=refunds)

            # Roll up daily schedule to monthly schedule
            monthly_schedule = rollup_month(revrec_schedule)

            # Save monthly schedule to monthly_entry Mongo collection
            for month, values in monthly_schedule.iteritems():
                yearmonth = month.split('-')
                m = MonthlyEntry(account_id=invoice.account_id,
                                 invoice_item_id=item.item_id,
                                 month=int(yearmonth[1]),
                                 year=int(yearmonth[0]),
                                 cr_rev=values['cr_rev'],
                                 ending_defrev=values['ending_defrev'],
                                 cr_ref_payable=values['cr_ref_payable'],
                                 dr_reserve_ref=values['dr_reserve_ref'],
                                 dr_contra_rev=values['dr_contra_rev'],
                                 dr_defrev=values['dr_defrev'],
                                 dr_reserve_graceperiod=values['dr_reserve_graceperiod'],
                                 cr_contra_rev=values['cr_contra_rev'])
                m.save()

    # Return dictionary
    if return_dict:
        return {
            'revrec_schedule': revrec_schedule,
            'invoice_items': invoice_items,
            'payment': payment,
            'refunds': refunds,
            'term_extensions': term_extensions,
            'gp_notes': gp_notes
        }

"""
--------------------
DICTIONARY ROLLUPS
--------------------
"""
def rollup_month(revrec_schedule):
    """Rolls up daily revenue schedule and returns a monthly schedule in dictionary form
    keyed on month, i.e. '2012-01'.

    :param revrec_schedule: Dictionary of debits and credits by day
    :return dict. Dictionary of debits and credits by month
    """
    rollup = {}
    dates = revrec_schedule.keys()
    start_date = min(dates)
    end_date = max(dates)
    for date, value in revrec_schedule.iteritems():
        key = '%s-%s' % (date.year, date.month)
        try:
            rollup[key]['cr_rev'] += value['cr_rev']
            rollup[key]['cr_ref_payable'] += value['cr_ref_payable']
            rollup[key]['dr_reserve_ref'] += value['dr_reserve_ref']
            rollup[key]['dr_contra_rev'] += value['dr_contra_rev']
            rollup[key]['dr_defrev'] += value['dr_defrev']
            rollup[key]['dr_reserve_graceperiod'] += value['dr_reserve_graceperiod']
            rollup[key]['cr_contra_rev'] += value['cr_contra_rev']
        except KeyError:
            rollup[key] = { 
                'cr_rev': value['cr_rev'], 
                'ending_defrev': 0,
                'cr_ref_payable': value['cr_ref_payable'],
                'dr_reserve_ref': value['dr_reserve_ref'],
                'dr_contra_rev': value['dr_contra_rev'],
                'dr_defrev': value['dr_defrev'],
                'dr_reserve_graceperiod': value['dr_reserve_graceperiod'],
                'cr_contra_rev': value['cr_contra_rev']
            }
        if date.day == monthrange(date.year, date.month)[1]:
            rollup[key]['ending_defrev'] = value['ending_defrev']	
    return rollup

"""
--------------------
MONGODB OPERATIONS
--------------------
"""
def connect_db():
    """Connect to Mongo database.

    Currently set for localhost.
    """
    connection = pymongo.Connection('localhost', 27017)
    db = connection['revrec']
    return db

def mapreduce(db):
    """Mongo map reduce query to compute totals.

    :param db: Pymongo db object.
    """
    revenue = MonthlyEntry.objects.sum('cr_rev')
    print 'Total revenue = $%s' % revenue

    results = db['monthly_entry'].group(key={'year':True, 'month':True},
                                        condition={},
                                        initial= {
                                            'cr_rev': 0, 
                                            'ending_defrev': 0, 
                                            'cr_ref_payable': 0,
                                            'dr_reserve_ref': 0,
                                            'dr_contra_rev': 0,
                                            'dr_defrev': 0,
                                            'dr_reserve_graceperiod': 0,
                                            'cr_contra_rev': 0
                                        },
                                        reduce= 'function(doc,out){ \
                                            out.cr_rev+=doc.cr_rev; \
                                            out.ending_defrev+=doc.ending_defrev; \
                                            out.cr_ref_payable+=doc.cr_ref_payable; \
                                            out.dr_reserve_ref+=doc.dr_reserve_ref; \
                                            out.dr_contra_rev+=doc.dr_contra_rev; \
                                            out.dr_defrev+=doc.dr_defrev; \
                                            out.dr_reserve_graceperiod+=doc.dr_reserve_graceperiod; \
                                            out.cr_contra_rev+=doc.cr_contra_rev; \
                                            }',
                                        finalize='')
    print 'Mapreduce results = '
    pprint.pprint(results)

"""
-------------------------
COMMAND LINE EXECUTABLE
-------------------------
"""
if __name__ == '__main__':
    print 'Running revenue recognition module...'
    db = connect_db()
    seed_db(db)
    recognize_revenue()
    mapreduce(db)