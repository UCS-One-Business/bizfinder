{
    'name': 'Bizfinder AI Event Triage',
    'summary': 'Experimental: TypeSafe Jev classifies Bizfinder company '
               'events (opportunity, follow-up, informational) and books '
               'follow-up activities for the ones worth a call.',
    'author': 'UCS OneDo AB',
    'website': 'https://www.ucsonedo.se',
    'category': 'Sales/CRM',
    'version': '19.0.1.0.0',
    # Glue addon: bizfinder itself stays free of ucs_core (web_gantt) so it
    # remains installable on community. The Jev client and key live in
    # ucs_core.
    'depends': ['bizfinder', 'ucs_core'],
    'data': [
        'views/bizfinder_settings_views.xml',
        'views/bizfinder_event_views.xml',
    ],
    'license': 'OPL-1',
    'application': False,
    'installable': True,
}
