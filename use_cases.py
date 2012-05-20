from __future__ import division
from datetime import datetime, timedelta, date
from helpers import daterange, pretty_date, days_elapsed, day_before, last_day_of_month

def amortize_amount(revrec_schedule, amt, start_date, end_date):
    """
    Modifies an existing revrec_schedule by amortizing the amount over the 
    specified period. Existing revenue and deferred revenue values will be 
    overwritten for the period.

    :param revrec_schedule: Dictionary of debits and credits by day
    :param amt: Amount of deferred revenue to be amortized.
   """

    daily_amort = amt / days_elapsed(start_date, end_date)
    defrev = amt

    for date in daterange(start_date, end_date):
        defrev = defrev - daily_amort
        revrec_schedule[date]['cr_rev'] = daily_amort
        revrec_schedule[date]['ending_defrev'] = defrev
        revrec_schedule[date]['dr_defrev'] = daily_amort

def amortize_service_fee(item, payment_date):
    """
    Creates a daily revenue recognition schedule for the specified invoice item
    based on daily amortization of deferred revenue to revenue.

    :param item: InvoiceItem object.
    :param payment_date: Date of payment.
    :return dict. Daily revrec schedule of debit and credit journal entries.
    """

    # Daily revenue recognition schedule
    revrec_schedule = {}

    # The amortization period begins on the day of the payment and continues 
    # until the end of the invoice item's service term
    revrec_start = max(payment_date, item.service_start)
    revrec_end = item.service_end

    # Fee amount
    amount = item.total_amount

    # Daily amortization of deferred revenue to revenue
    daily_amort = amount / days_elapsed(revrec_start, revrec_end)

    # Deferred revenue does not exist until payment is made
    defrev = 0
    rev = 0
    cumul_rev = 0

    # Generating revenue recognition schedule
    for date in daterange(item.service_start, revrec_end):

        # On payment date, set the deferred revenue balance
        # and daily revenue amortization
        if date == payment_date:
            defrev = amount
            rev = daily_amort
        # From payment date and onwards, amortize deferred revenue to revenue
        if date >= payment_date: 
            defrev = defrev - daily_amort
            cumul_rev += rev

        revrec_schedule[date] = {
            'cr_rev': rev,
            'dr_defrev': rev,
            'ending_defrev': defrev,
            'cumul_rev': cumul_rev,
            'cr_ref_payable': 0,
            'dr_reserve_ref': 0,
            'dr_contra_rev': 0,
            'dr_reserve_graceperiod': 0,
            'cr_contra_rev': 0
        }

    return revrec_schedule

def apply_grace_period(revrec_schedule, item, payment_date):
    """Adjusts the specified revrec schedule for late payment, which
    requires journal entries related to grace period.

    :param revrec_schedule: Dictionary of debits and credits by day
    :param item: InvoiceItem object
    :param payment_date: Date of payment
    """
    gp_notes = []

    service_start = item.service_start
    service_end = item.service_end

    billperiod = item.billperiod
    shift = {'Monthly': 30, 'Yearly': 365, 'Biyearly': 730}

    previous_service_end = service_start - timedelta(1) 
    previous_service_start = previous_service_end - timedelta(shift[billperiod] - 1) 
    previous_service_term = (previous_service_end - previous_service_start).days + 1
    previous_amort = item.total_amount / previous_service_term

    current_reporting_day = datetime(service_start.year, service_start.month, 
                                     last_day_of_month(service_start.year, service_start.month))
    previous_reporting_day = datetime(previous_service_end.year, previous_service_end.month, 1) - timedelta(1)

    gp_notes.append('JOURNAL ENTRIES FOR GRACE PERIOD')
    gp_notes.append('---'*60)
    gp_notes.append('payment date: %s, current term: %s -> %s, previous term: %s -> %s' % (
        pretty_date(payment_date),
        pretty_date(service_start),
        pretty_date(service_end),
        pretty_date(previous_service_start),
        pretty_date(previous_service_end)))

    gp_notes.append('current reporting day: %s, previous reporting day: %s, days reserved for: %s -> %s' % (
        pretty_date(current_reporting_day), 
        pretty_date(previous_reporting_day),
        previous_service_start,
        previous_reporting_day))

    running_total = 0
    for date in daterange(service_start, payment_date - timedelta(1)):
        revised_service_term = previous_service_term + (date - service_start).days + 1
        revised_amort = item.total_amount / revised_service_term
        amort_difference = previous_amort - revised_amort
        revised_dr_reserve_graceperiod = ((previous_reporting_day - previous_service_start).days + 1) * amort_difference
        dr_reserve_graceperiod = revised_dr_reserve_graceperiod - running_total
        cr_contra_rev = dr_reserve_graceperiod

        revrec_schedule[date]['dr_reserve_graceperiod'] = dr_reserve_graceperiod
        revrec_schedule[date]['cr_contra_rev'] = cr_contra_rev

        gp_notes.append('%s, PrevTerm: %s->%s, PrevAmort: $%s->$%s, Value: %s, DaysReservedFor: %s, \
                        PrevTotalReserve %s, TotalReserve: %s, DR reserve: %s' % (
            pretty_date(date),
            previous_service_term,
            revised_service_term,
            round(previous_amort, 3),
            round(revised_amort, 3),
            revised_service_term * revised_amort,
            (previous_reporting_day - previous_service_start).days + 1,
            round(running_total, 3),
            round(revised_dr_reserve_graceperiod, 3),
            round(dr_reserve_graceperiod,3)))
        running_total += dr_reserve_graceperiod
    gp_notes.append('---'*60)
    return gp_notes

def apply_refunds(revrec_schedule, invoice_amount, item, refunds):
    """Adjusts the specified revrec schedule for refunds.

    :param revrec_schedule: Dictionary of debits and credits by day
    :param invoice_amount: Total amount of the invoice
    :param item: The Item object
    :param refunds: Refund objects
    """
    # Adjustment amortization due to refunds
    for ref in refunds:

        proportion = item.total_amount/invoice_amount
        refund_applied = ref.refund_amount * proportion

        last_day_of_schedule = max(revrec_schedule.keys())

        # Deferred revenue and total revenue recognized as of beginning of refund date
        stats_as_of_refund_date = {
            'ending_defrev': revrec_schedule[day_before(ref.refund_date)]['ending_defrev'],
            'cr_rev': sum([row['cr_rev'] for date, row 
                 in revrec_schedule.iteritems() if date < ref.refund_date]) 
        }

        # positive_item_amount: is the invoice item a charge vs. discount/pro-rated credit?
        # service_cancelled: is refund related to service being cancelled?
        flags = {
            'positive_item_amount': item.total_amount >= 0,
            'service_cancelled': ref.cancel_flag
        }

        # Calculate debits and credits associated with refund event
        results = refund_calc(flags=flags, 
                              revrec_start_date=min(revrec_schedule.keys()), 
                              refund_date=ref.refund_date, 
                              refund_amount=refund_applied,
                              stats_as_of_refund_date=stats_as_of_refund_date)

        # Remaining deferred revenue
        remaining_defrev = stats_as_of_refund_date['ending_defrev'] - results['dr_defrev']

        # Copy over results of refund calculation to schedule; debits/credits are effective the refund day
        for (key, value) in results.iteritems():
            revrec_schedule[ref.refund_date][key] = value

        # If service term is cancelled, any remaining deferred revenue is recognized on the day of the refund
        if ref.cancel_flag:
            revrec_schedule[ref.refund_date]['cr_rev'] = remaining_defrev 
            revrec_schedule[ref.refund_date]['cumul_rev'] = revrec_schedule[ref.refund_date - 
                timedelta(1)]['cumul_rev'] + remaining_defrev
            revrec_schedule[ref.refund_date]['ending_defrev'] = 0

            # Now that DR is zeroed out, there is no more amortization
            # print 'Clearing schedule from %s to %s' % (ref.refund_date + timedelta(1), last_day_of_schedule)
            for date in daterange(ref.refund_date + timedelta(1), last_day_of_schedule):
                revrec_schedule[date]['cr_rev'] = 0
                revrec_schedule[date]['ending_defrev'] = 0
                revrec_schedule[date]['cumul_rev'] = 0
                revrec_schedule[date]['dr_defrev'] = 0

        # If service term not cancelled, remaining deferred revenue is amortized through end of service term
        else:
            amortize_amount(revrec_schedule=revrec_schedule, 
                            amt=remaining_defrev, 
                            start_date=ref.refund_date, 
                            end_date=last_day_of_schedule)

def refund_calc(flags, revrec_start_date, refund_date, refund_amount, stats_as_of_refund_date):
    """Returns a dictionary of debit and credit journal entries associated with the refund that take effect 
    on the day of the refund.

    Accounting treatment depends on whether or not service is cancelled at the time of the refund. If so, 
    then the refund is applied against deferred revenue first, then revenue that is already recognized. 
    This is the case of cancellation refunds.

    On the other hand, if service continues after the refund, then the refund is applied against revenue 
    first, then deferred revenue. This is the case of refunds for customer service issues.

    :param flags.positive_item_amount: TRUE if the amount of the invoice item is positive. If negative, then 
                                       the item is a discount or credit, in which case the calculations are 
                                       different.
    :param flags.cancel_flag: TRUE if the refund is related to a cancellation of service.
    :param revrec_start_date: Date from which revenue recognition begins. This is the max of invoice item 
                              service start date and payment date.
    :param refund_date: Date of refund.
    :param as_of_refund_date.cr_rev: Revenue recognized on the invoice item as of the beginning of the 
                                     refund date.
    :param as_of_refund_date.ending_defrev: Deferred revenue balance at the beginning of the refund date.
    :param refund_amount: Amount of the refund (part of Refund object).
    :return dict. Contains calculated debit and credit journal entries associated with the refund: 
                  DR deferred revenue, DR reserve for refunds, DR contra-revenue, CR refunds payable.
    """

    days_serviced_total = (refund_date - revrec_start_date).days
    days_serviced_in_month = min(refund_date.day - 1, days_serviced_total)

    positive_item_amount = flags['positive_item_amount']
    service_cancelled = flags['service_cancelled']

    defrev = abs(stats_as_of_refund_date['ending_defrev'])
    rev = abs(stats_as_of_refund_date['cr_rev'])

    # Service term is cancelled, refund goes against deferred revenue first
    if service_cancelled:

        # Debit to deferred revenue
        dr_defrev = min(refund_amount, defrev)

        # Refund of revenue
        refund_of_revenue = max(0, refund_amount - dr_defrev)

    # Service term continues, refund goes against revenue first
    else:

        # Refund of revenue
        refund_of_revenue = min(refund_amount, rev)

        # Debit to deferred revenue
        dr_defrev = refund_amount - refund_of_revenue

    # print 'days_serviced_in_month: %s, days_serviced_total: %s' % (days_serviced_in_month, days_serviced_total)

    # Debit to contra-revenue
    dr_contra_rev = refund_of_revenue * days_serviced_in_month / days_serviced_total 

    # Debit to reserve for expected refunds
    dr_reserve_ref = refund_of_revenue - dr_contra_rev

    # Return journal entries
    journal_entries = { 
        'dr_defrev': dr_defrev,
        'dr_reserve_ref': dr_reserve_ref,
        'dr_contra_rev': dr_contra_rev,
        'cr_ref_payable': refund_amount
    }

    return journal_entries	

def apply_term_extensions(item, revrec_schedule, term_extensions):
    """Adjusts the specified revrec schedule for term extensions.

    :param item: InvoiceItem object.
    :param revrec_schedule: Dictionary of debits and credits by day
    :param term_extensions: Term Extension objects.

    """
    for ext in term_extensions:
        defrev = revrec_schedule[ext.grant_date - timedelta(1)]['ending_defrev']

        start = ext.grant_date
        end = ext.service_end
        daily_amort = defrev / ((end - start).days + 1)

        for date in daterange(start, end):
            defrev = defrev - daily_amort
            template =  {
                'cr_rev': daily_amort,
                'ending_defrev': defrev,
                'cr_ref_payable': 0,
                'dr_reserve_ref': 0
            }
            try:
                revrec_schedule[date]['cr_rev'] = daily_amort
                revrec_schedule[date]['ending_defrev'] = defrev
            except KeyError:
                revrec_schedule[date] = template