ROLE_PERMISSIONS = {
    "CEO": ["all"],
    "Vice CEO": ["all"],
    "General Manager": ["all"],
    "Vice General Manager": ["all"],
    "Bid Manager": ["workspace", "tasks", "tender", "reports"],
    "Bid Operator": ["workspace", "tasks", "tender"],
    "ICT Coordinator": ["workspace", "tasks", "employees", "reports"],
    "Legal Counsel": ["workspace", "tasks", "tender", "documents"],
    "HR": ["workspace", "tasks", "employees", "reports"],
    "Import Manager": ["workspace", "tasks", "tender", "suppliers", "landed_costs", "receiving"],
    "Case Executive": ["workspace", "tasks", "documents"],
    "Office Assistant": ["workspace", "tasks", "documents", "inventory"],
    "Finance Manager": ["workspace", "tasks", "accounting", "journal", "invoices", "landed_costs", "reports", "customers"],
    "Accountant": ["workspace", "tasks", "accounting", "journal"]
}

def get_visible_modules(job_title):
    if not job_title: return ['workspace', 'tasks']
    for role, modules in ROLE_PERMISSIONS.items():
        if role in job_title:
            return modules
    return ['workspace', 'tasks']
