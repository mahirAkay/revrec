from flask import Flask, render_template, jsonify, request
from revrec import connect_db, process_invoice
from seed import seed_db
from models import Invoice
from helpers import pretty_date
app = Flask(__name__)

@app.route('/')
def index():
    db = connect_db()
    seed_db(db)
    invoice = Invoice.objects().first()
    results = process_invoice(invoice=invoice, return_dict=True)

    labels = ['Date', 'Ending Def Rev', 'Cumulative Revenue', 'CR Sales Revenue', 'DR Deferred Revenue', 
              'DR Reserve Refunds', 'DR Contra-Revenue', 'CR Refunds Payable', 'DR Reserve Grace Period',
              'CR Contra-Revenue']
    data = []
    for (date, v) in sorted(results['revrec_schedule'].iteritems(), key=lambda (k, v): (k, v)):
        row = [pretty_date(date), 
               v['ending_defrev'], 
               v['cumul_rev'],
               v['cr_rev'], 
               v['dr_defrev'], 
               v['dr_reserve_ref'], 
               v['dr_contra_rev'], 
               v['cr_ref_payable'],
               v['dr_reserve_graceperiod'],
               v['cr_contra_rev']]
        data.append(row)

    return render_template('base.html', 
                            labels=labels,
                            data=data,
                            invoice=invoice,
                            payment=results['payment'],
                            invoice_items=results['invoice_items'],
                            refunds=results['refunds'],
                            gp_notes=results['gp_notes'])


@app.context_processor
def utility_processor():
    """Formats a number into a price in U.S. $ currency.
    """
    def format_price(amount):
        return u'${0:.2f}'.format(amount)
    return dict(format_price=format_price) 

if __name__ == '__main__':
    app.run(debug=True)