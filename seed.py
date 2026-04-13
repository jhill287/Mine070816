"""
Run this once to populate the app with 5 realistic Colorado test deals.
Usage: python3 seed.py
"""

from app import app, init_db
import json

init_db()
client = app.test_client()

deals = [
    {
        'tx': {
            'address': '2847 Spruce Canyon Dr', 'city': 'Boulder', 'state': 'CO', 'zip_code': '80304',
            'mls_number': '7823041', 'type': 'buyer', 'status': 'under_contract',
            'mec_date': '2026-04-03', 'closing_date': '2026-05-03', 'possession_date': '2026-05-03',
            'purchase_price': 875000, 'earnest_money': 17500,
            'client_name': 'Marcus & Priya Whitfield', 'client_phone': '720-555-0182',
            'client_email': 'mwhitfield@gmail.com', 'agent_name': 'Your Name',
            'lender_name': 'Elevations Credit Union', 'lender_phone': '303-443-4672',
            'lender_email': 'jsmith@elevationscu.com',
            'title_company': 'Land Title Guarantee', 'title_contact': 'Karen Hollis',
            'title_phone': '303-321-1880', 'other_agent_name': 'Dana Reeves',
            'other_agent_phone': '303-555-0247', 'tc_name': 'Stephanie Cruz',
            'tc_email': 'scruz@transactionpro.com', 'hoa_name': 'Spruce Canyon HOA',
            'notes': 'Buyers relocating from Chicago. Pre-approved at 6.875%. HOA docs needed ASAP.',
        },
        'template': 'co_cbs_buyer_30',
        'extra': [
            {'title': 'Schedule Home Inspection', 'due_date': '2026-04-06', 'category': 'inspection',
             'priority': 'high', 'description': 'Book inspector — buyers prefer weekend', 'due_time': '12:00'},
            {'title': 'Order HOA Resale Certificate', 'due_date': '2026-04-05', 'category': 'hoa',
             'priority': 'medium', 'description': 'Contact Spruce Canyon HOA directly — 303-555-0100'},
        ],
    },
    {
        'tx': {
            'address': '514 W Mulberry St', 'city': 'Fort Collins', 'state': 'CO', 'zip_code': '80521',
            'mls_number': '6109834', 'type': 'seller', 'status': 'under_contract',
            'mec_date': '2026-03-28', 'closing_date': '2026-04-27', 'possession_date': '2026-04-27',
            'purchase_price': 545000, 'earnest_money': 10000,
            'client_name': 'Robert & Linda Garrett', 'client_phone': '970-555-0314',
            'client_email': 'rgarrett@outlook.com', 'agent_name': 'Your Name',
            'lender_name': 'N/A — Cash Offer', 'title_company': 'Stewart Title',
            'title_contact': 'Mike Torres', 'title_phone': '970-221-4800',
            'other_agent_name': 'Chris Nakamura', 'other_agent_phone': '970-555-0198',
            'tc_name': 'Stephanie Cruz', 'tc_email': 'scruz@transactionpro.com',
            'notes': 'Cash offer — no appraisal contingency. Sellers need 30-day post-close occupancy. Repair request came in at $8k, countered at $3,500 credit.',
        },
        'template': 'co_cbs_seller_30',
        'extra': [
            {'title': 'Confirm Repair Credit in Closing Disclosure', 'due_date': '2026-04-24',
             'category': 'closing', 'priority': 'high',
             'description': '$3,500 seller credit agreed — verify it appears on final CD'},
            {'title': 'Seller Post-Close Occupancy Agreement Signed', 'due_date': '2026-04-10',
             'category': 'custom', 'priority': 'high',
             'description': 'PCOA for 30 days at $75/day must be executed before closing'},
        ],
    },
    {
        'tx': {
            'address': '19203 E Caley Dr', 'city': 'Aurora', 'state': 'CO', 'zip_code': '80016',
            'mls_number': '4457720', 'type': 'buyer', 'status': 'under_contract',
            'mec_date': '2026-04-07', 'closing_date': '2026-05-22', 'possession_date': '2026-05-22',
            'purchase_price': 610000, 'earnest_money': 12000,
            'client_name': 'Devon Okafor', 'client_phone': '720-555-0091',
            'client_email': 'dokafor@icloud.com', 'agent_name': 'Your Name',
            'lender_name': 'Cherry Creek Mortgage', 'lender_phone': '303-595-0111',
            'lender_email': 'tpatel@cherrycreekmortgage.com',
            'title_company': 'Fidelity National Title', 'title_contact': 'Amy Weston',
            'title_phone': '303-744-3200', 'other_agent_name': 'Paula Simmons',
            'other_agent_phone': '720-555-0362', 'tc_name': 'Stephanie Cruz',
            'tc_email': 'scruz@transactionpro.com', 'hoa_name': "Tallyn's Reach Metro District",
            'notes': 'FHA loan — appraisal must hit $610k. First-time buyer, needs extra communication. 45-day close to accommodate lender timeline.',
        },
        'template': 'co_cbs_buyer_45',
        'extra': [
            {'title': 'Confirm FHA Appraisal Ordered', 'due_date': '2026-04-14',
             'category': 'appraisal', 'priority': 'high',
             'description': 'Follow up with Cherry Creek — FHA appraisals take longer, order early'},
            {'title': 'First-Time Buyer Education Course Complete', 'due_date': '2026-04-21',
             'category': 'financing', 'priority': 'medium',
             'description': 'Required by lender for this FHA product — confirm certificate submitted'},
        ],
    },
    {
        'tx': {
            'address': '78 Redstone Ct', 'city': 'Highlands Ranch', 'state': 'CO', 'zip_code': '80126',
            'mls_number': '2298815', 'type': 'seller', 'status': 'active',
            'purchase_price': 725000, 'client_name': 'Tom & Sarah Nguyen',
            'client_phone': '303-555-0447', 'client_email': 'tnguyen@gmail.com',
            'agent_name': 'Your Name', 'title_company': 'Land Title Guarantee',
            'tc_name': 'Stephanie Cruz', 'tc_email': 'scruz@transactionpro.com',
            'hoa_name': 'Highlands Ranch Community Association',
            'notes': 'Active listing — went live 4/10. Two showings scheduled this weekend. Sellers motivated, moving to Phoenix.',
        },
        'template': None,
        'extra': [
            {'title': 'Review Showing Feedback', 'due_date': '2026-04-14', 'category': 'custom',
             'priority': 'medium', 'description': 'Compile weekend showing feedback and call sellers'},
            {'title': 'Week-1 Listing Price Review', 'due_date': '2026-04-17', 'category': 'custom',
             'priority': 'medium', 'description': 'If no offers by end of week 1, discuss price reduction'},
            {'title': 'Seller Disclosure Signed & Delivered', 'due_date': '2026-04-10',
             'category': 'disclosure', 'priority': 'high',
             'description': 'Ensure all disclosures are completed and in Skyslope'},
        ],
    },
    {
        'tx': {
            'address': '3301 Arapahoe Ave Unit 215', 'city': 'Boulder', 'state': 'CO', 'zip_code': '80303',
            'mls_number': '9934402', 'type': 'buyer', 'status': 'closed',
            'mec_date': '2026-02-14', 'closing_date': '2026-03-16', 'possession_date': '2026-03-16',
            'purchase_price': 420000, 'earnest_money': 8000,
            'client_name': 'Alicia Fernandez', 'client_phone': '720-555-0773',
            'client_email': 'alicia.f@gmail.com', 'agent_name': 'Your Name',
            'lender_name': 'US Bank Home Mortgage', 'lender_phone': '303-585-5000',
            'lender_email': 'kwilson@usbank.com', 'title_company': 'Pinnacle Title',
            'title_contact': 'Brian Lee', 'title_phone': '303-442-9000',
            'other_agent_name': 'James Ortega', 'other_agent_phone': '303-555-0512',
            'tc_name': 'Stephanie Cruz', 'tc_email': 'scruz@transactionpro.com',
            'hoa_name': 'Arapahoe Village Condos',
            'notes': 'CLOSED 3/16/2026. Condo purchase. Smooth transaction — no inspection issues. Buyer very happy.',
        },
        'template': 'co_cbs_buyer_30',
        'extra': [],
        'mark_complete': True,
    },
]

print('Loading test data...')
print()

for deal in deals:
    r  = client.post('/api/transactions', json=deal['tx'])
    tx = json.loads(r.data)
    tid = tx['id']
    print(f"  {deal['tx']['address']}, {deal['tx']['city']}  [{deal['tx']['status'].upper()}]")

    if deal['template'] and deal['tx'].get('mec_date'):
        client.post(f'/api/transactions/{tid}/apply-template', json={
            'template': deal['template'], 'mec_date': deal['tx']['mec_date']
        })

    for dl in deal.get('extra', []):
        client.post(f'/api/transactions/{tid}/deadlines', json={**dl, 'status': 'pending'})

    if deal.get('mark_complete'):
        tx_full = json.loads(client.get(f'/api/transactions/{tid}').data)
        for d in tx_full['deadlines']:
            client.post(f'/api/deadlines/{d["id"]}/status', json={'status': 'completed'})
        print(f'    → All deadlines marked complete (closed deal)')

print()
print('Done! Refresh http://localhost:5000 to see the data.')
