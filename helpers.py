from __future__ import division
import random
import math
from datetime import datetime, timedelta
from calendar import isleap

"""
-------------------
HELPER FUNCTIONS
-------------------
"""
def daterange(start_date, end_date):
    """A generator that yields an iterator containing dates within the specified date range,
    inclusive of the endpoints.

    :param start_date: Start date of date range. Included within resulting iterator.
    :param end_date: End date of date range. Included within resulting iterator.
    """
    for n in range(days_elapsed(start_date, end_date)):
        yield start_date + timedelta(n)

def days_elapsed(start_date, end_date):
    """
    :param start_date: Start date of calculation.
    :param end_date: End date of calculation.
    :return int. Number of days elapsed between two dates, inclusive of the endpoints.
    """
    return (end_date - start_date).days + 1

def day_before(datetime):
    """
    :param datetime: A python datetime.
    :return datetime. The datetime representing the date prior to the specified parameter.
    """
    return datetime - timedelta(1)

def pretty_date(datetime):
    """
    :param datetime: A python datetime.
    :return string. The specified python datetime converted to "YYYY-MM-DD".
    """
    return str(datetime)[:10]

def get_next_renewal_date(initial_bill_date, prev_renewal_date, billperiod_in_months):
    """
    Given the initial bill date, the previous bill date and a billing period, returns the 
    next renewal date. This is based on anniversary date renewals, i.e. for a monthly 
    renewing subscription:

        [Mar 5 -> Apr 5; Mar 15 -> Apr 15; Mar 30 -> Apr 30, Mar 31 -> Apr 30]

    :param initial_bill_date: The date of the initial service fee, from which the bill
    	                      cycle day is based.
    :param prev_renewal_date: The renewal date that immediately preceded the renewal date we
    						  are trying to calculate.
    :param billperiod_in_months: The length of the billperiod.
    :return datetime. The next renewal date.
    """

    sum_months = prev_renewal_date.month + billperiod_in_months
    next_renewal_year = int(prev_renewal_date.year + math.ceil(sum_months / 12 - 1))
    if sum_months % 12 == 0:
        next_renewal_month = 12
    else:
        next_renewal_month = sum_months % 12

    last_day_of_nrm = last_day_of_month(next_renewal_year, next_renewal_month)
    if is_last_day_of_month(initial_bill_date) or last_day_of_nrm < initial_bill_date.day:
        next_renewal_day = last_day_of_nrm
    else:
        next_renewal_day = initial_bill_date.day

    return datetime(next_renewal_year, next_renewal_month, next_renewal_day)

def last_day_of_month(year, month):
    """Returns the last day of the month.
    :param year: A year.
    :param month: A month.
    :return int. Given the year and the month, returns the last day of that month.
    """
    last_day = {1:31, 2:28, 3:31, 4:30, 5:31, 6:30, 7:31, 8:31, 9:30, 10:31, 11:30, 12:31}
    last_day_leap = dict(last_day)
    last_day_leap[2] = 29

    if isleap(year):
        return last_day_leap[month]
    else:
        return last_day[month]

def is_last_day_of_month(dte):
    """Checks if a datetime is the last day of the month.
    :param dte: A datetime.
    :return boolean. Returns True if the date is the last day of the month, else False.
    """
    next_day = dte + timedelta(1)
    if dte.month != next_day.month:
        return True
    else:
        return False

def gen_id():
    """Returns a randomized 8-character numeric id.
    :return string. A randomized id.
    """
    return ''.join(random.choice('0123456789') for i in range(8))