# -*- coding: utf-8 -*-
{
    'name': 'Bizfinder',
    'summary': 'Creditsafe-backed lead generation wizard (PoC).',
    'description': """
Search Swedish company registry data sourced from Creditsafe via the
bizfinder_api FastAPI service. Filter on region, SNI industry, legal form,
turnover and employee buckets, plus growth and solidity. Convert selected
prospects into crm.lead records.
""",
    'author': 'UCS OneDo AB',
    'website': 'https://www.ucsonedo.se',
    'category': 'Sales/CRM',
    'version': '19.0.1.0.11',
    'depends': ['base', 'web', 'crm'],
    'data': [
        'security/ir.model.access.csv',
        'data/bizfinder_region_data.xml',
        'views/bizfinder_settings_views.xml',
        'views/bizfinder_wizard_views.xml',
        'views/bizfinder_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bizfinder/static/src/js/bizfinder_search_form.js',
            'bizfinder/static/src/scss/bizfinder_search.scss',
        ],
    },
    'license': 'OPL-1',
    'application': True,
    'installable': True,
}
