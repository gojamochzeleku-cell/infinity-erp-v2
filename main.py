import urllib.request
import json
import os
import hashlib
from datetime import datetime, timedelta
from typing import List

from fastapi import FastAPI, Depends, Request, Form, HTTPException, Cookie, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import engine, get_db, Base
from role_permissions import get_visible_modules
import models

# Create tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Infinity ERP v2")
templates = Jinja2Templates(directory="templates")
templates.env.globals['get_visible_modules'] = get_visible_modules

# --- AUTHENTICATION & SECURITY ---

def get_current_company_id(request: Request) -> int:
    cid = request.cookies.get("company_id")
    return int(cid) if cid and cid.isdigit() else 1

def get_password_hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# Custom exception handler to cleanly redirect unauthenticated users

import json

@app.exception_handler(307)
async def auth_redirect_handler(request: Request, exc: HTTPException):
    return RedirectResponse(url="/login", status_code=303)

def get_current_employee(db: Session = Depends(get_db), emp_id_cookie: str = Cookie(None, alias="emp_id")):
    if not emp_id_cookie:
        raise HTTPException(status_code=307)
    try:
        emp = db.query(models.Employee).filter(
            models.Employee.id == int(emp_id_cookie), 
            models.Employee.is_active == True
        ).first()
        if not emp:
            raise HTTPException(status_code=307)
        return emp
    except Exception:
        raise HTTPException(status_code=307)

def require_company_access(employee: models.Employee, target_company_id: int):
    if employee.role != "ADMIN" and employee.company_id != target_company_id:
        raise HTTPException(status_code=403, detail=f"Access denied to company ID {target_company_id}")

def get_workspace_items(db, current_emp, model, company_id):
    return db.query(model).filter(
        (model.created_by == current_emp.id) | (model.assigned_to == current_emp.id)
    ).order_by(model.created_at.desc() if hasattr(model, 'created_at') else model.id.desc()).all()

def seed_data(db: Session):
    if db.query(models.Company).count() == 0:
        c1 = models.Company(code="INFINITY", name="Infinity Investment Institute")
        c2 = models.Company(code="CAPITAL_HAILU", name="Capital Hailu Import")
        c3 = models.Company(code="YIRGA_AGEDOM", name="Yirga Agedom Haile Import")
        db.add_all([c1, c2, c3])
        db.commit()
        
        e1 = models.Employee(
            name="Admin User", company_id=1, role="ADMIN", is_active=True, language="en", 
            username="admin", password_hash=get_password_hash("admin123"), job_title="General Manager"
        )
        db.add(e1)
        db.commit()

        accounts = [
            models.Account(company_id=1, account_code="1000", account_name="Cash in Bank", account_type="ASSET", balance=0.0, is_active=True),
            models.Account(company_id=1, account_code="2000", account_name="Accounts Payable", account_type="LIABILITY", balance=0.0, is_active=True),
            models.Account(company_id=1, account_code="4000", account_name="Sales Revenue", account_type="REVENUE", balance=0.0, is_active=True),
            models.Account(company_id=1, account_code="5000", account_name="Office Expenses", account_type="EXPENSE", balance=0.0, is_active=True)
        ]
        db.add_all(accounts)
        db.commit()

        w1 = models.Warehouse(company_id=1, name="Main Warehouse", location="Addis Ababa HQ", is_active=True)
        db.add(w1)
        db.commit()
        
        items = [
            models.InventoryItem(company_id=1, item_code="ITM-001", item_name="Dell Laptops", category="Electronics", unit_of_measure="PCS", current_stock=0.0, unit_cost=45000.0, is_active=True),
            models.InventoryItem(company_id=1, item_code="ITM-002", item_name="Wireless Mice", category="Accessories", unit_of_measure="PCS", current_stock=0.0, unit_cost=1500.0, is_active=True)
        ]
        db.add_all(items)
        db.commit()

        po1 = models.PurchaseOrder(po_number="PO-2026-001", company_id=1, status="ISSUED")
        db.add(po1)
        db.commit()
        db.add_all([
            models.POLine(po_id=po1.id, item_name="Dell Laptops", ordered_qty=10.0, received_qty=0.0),
            models.POLine(po_id=po1.id, item_name="Wireless Mice", ordered_qty=50.0, received_qty=0.0)
        ])
        db.commit()

        t1 = models.Tender(
            company_id=1, title="UNICEF Water Purification Supply Tender", client_name="UNICEF Ethiopia",
            description="Supply and deliver 500 industrial water purification units.",
            bid_amount=1250000.00, status="SUBMITTED", created_by=1, assigned_to=1
        )
        db.add(t1)
        db.commit()
@app.on_event("startup")
def startup_event():
    db = next(get_db())
    seed_data(db)

# --- AUTH ROUTES ---
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})
@app.post("/login")
def process_login(request: Request, username: str = Form(...), password: str = Form(...), company_id: int = Form(...), db: Session = Depends(get_db)):
    emp = db.query(models.Employee).filter(models.Employee.username == username, models.Employee.password_hash == get_password_hash(password), models.Employee.is_active == True).first()
    if not emp: return templates.TemplateResponse(request, "login.html", {"error": "Invalid credentials"})
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="emp_id", value=str(emp.id), httponly=True, max_age=86400)
    response.set_cookie(key="company_id", value=str(company_id), httponly=True, max_age=86400)
    return response
@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="emp_id")
    response.delete_cookie(key="company_id")
    return response
@app.post("/api/switch-company")
def switch_company(company_id: int = Form(...), db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)):
    # Verify employee has access to this company
    if current_emp.role != "ADMIN" and current_emp.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied to this company")
    response = RedirectResponse(url="/workspace", status_code=303)
    response.set_cookie(key="company_id", value=str(company_id), httponly=True, max_age=86400)
    return response

# --- DASHBOARD ---
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    active_pos = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.status != 'RECEIVED', models.PurchaseOrder.company_id == company_id).count()
    pending_tasks = db.query(models.Task).filter(models.Task.status != 'DONE', models.Task.company_id == company_id).count()
    total_employees = db.query(models.Employee).filter(models.Employee.is_active == True, models.Employee.company_id == company_id).count()
    inventory_items = db.query(models.InventoryItem).filter(models.InventoryItem.company_id == company_id).all()
    total_inventory_value = sum(item.current_stock * item.unit_cost for item in inventory_items)

    return templates.TemplateResponse(request, "dashboard.html", {
        "active": "dashboard", "current_emp": current_emp,
        "active_pos": active_pos, "pending_tasks": pending_tasks,
        "total_employees": total_employees, "total_inventory_value": total_inventory_value
    })

# --- EMPLOYEES ---
@app.get("/employees", response_class=HTMLResponse)
def employees_page(request: Request, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)):
    require_company_access(current_emp, 1)
    employees = db.query(models.Employee).all()
    companies = db.query(models.Company).all()
    return templates.TemplateResponse(request, "employees.html", {"active": "employees", "current_emp": current_emp, "employees": employees, "companies": companies})
@app.post("/api/employees")
def create_employee(name: str = Form(...), company_id: int = Form(...), role: str = Form(...), language: str = Form("en"), db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)):
    require_company_access(current_emp, company_id)
    db.add(models.Employee(name=name, company_id=company_id, role=role, is_active=True, language=language, username=name.lower().replace(" ", "_"), password_hash=get_password_hash("123456")))
    db.commit()
    return RedirectResponse(url="/employees?success=true", status_code=303)
@app.post("/api/employees/{emp_id}/toggle")
def toggle_employee_status(emp_id: int, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)):
    emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
    if not emp: raise HTTPException(status_code=404, detail="Employee not found")
    require_company_access(current_emp, emp.company_id)
    emp.is_active = not emp.is_active
    db.commit()
    return RedirectResponse(url="/employees", status_code=303)

# --- GOODS RECEIVING ---
@app.get("/receiving", response_class=HTMLResponse)
def receiving_page(request: Request, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    pos = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.company_id == company_id).all()
    pos_data = [{"id": po.id, "po_number": po.po_number, "status": po.status, "lines": [{"id": line.id, "item_name": line.item_name, "ordered_qty": line.ordered_qty, "received_qty": line.received_qty} for line in po.lines]} for po in pos]
    po_ids = [p.id for p in pos]
    receipts = db.query(models.Receipt).filter(models.Receipt.po_id.in_(po_ids)).order_by(models.Receipt.received_at.desc()).all() if po_ids else []
    return templates.TemplateResponse(request, "receiving.html", {"active": "receiving", "current_emp": current_emp, "pos": pos_data, "receipts": receipts})
@app.post("/api/receipts")
def create_receipt(receipt_number: str = Form(...), po_id: int = Form(...), line_ids: List[int] = Form(...), received_qtys: List[float] = Form(...), notes: str = Form(""), db: Session = Depends(get_db)):
    if db.query(models.Receipt).filter(models.Receipt.receipt_number == receipt_number).first():
        raise HTTPException(status_code=400, detail="Receipt number already exists")

    receipt = models.Receipt(receipt_number=receipt_number, po_id=po_id, received_by=1, notes=notes)
    db.add(receipt)
    db.flush()
    po = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == po_id).first()

    for line_id, qty in zip(line_ids, received_qtys):
        if qty <= 0: continue
        po_line = db.query(models.POLine).filter(models.POLine.id == line_id, models.POLine.po_id == po_id).first()
        if not po_line: raise HTTPException(status_code=400, detail=f"Invalid line item {line_id}")
        if (po_line.received_qty + qty) > po_line.ordered_qty:
            raise HTTPException(status_code=400, detail=f"Cannot receive {qty}. Only {po_line.ordered_qty - po_line.received_qty} remaining.")
        
        db.add(models.ReceiptLine(receipt_id=receipt.id, po_line_id=po_line.id, received_qty=qty))
        po_line.received_qty += qty

        inv_item = db.query(models.InventoryItem).filter(models.InventoryItem.item_name == po_line.item_name, models.InventoryItem.company_id == po.company_id).first()
        if inv_item:
            inv_item.current_stock += qty
            db.add(models.StockMovement(company_id=po.company_id, item_id=inv_item.id, warehouse_id=1, movement_type="IN", quantity=qty, reference_type="RECEIPT", reference_id=receipt.id, notes=f"Received via {receipt_number}"))

    all_lines = db.query(models.POLine).filter(models.POLine.po_id == po_id).all()
    if all(line.received_qty >= line.ordered_qty for line in all_lines): po.status = "RECEIVED"
    elif any(line.received_qty > 0 for line in all_lines): po.status = "PARTIALLY_RECEIVED"

    db.commit()
    return RedirectResponse(url="/receiving?success=true", status_code=303)

# --- ACCOUNTING ---
@app.get("/accounts", response_class=HTMLResponse)
def accounts_page(request: Request, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    require_company_access(current_emp, 1)
    accounts = db.query(models.Account).filter(models.Account.company_id == company_id).all()
    return templates.TemplateResponse(request, "accounts.html", {"active": "accounts", "current_emp": current_emp, "accounts": accounts})
@app.post("/api/accounts")
def create_account(account_code: str = Form(...), account_name: str = Form(...), account_type: str = Form(...), db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    require_company_access(current_emp, 1)
    if db.query(models.Account).filter(models.Account.account_code == account_code).first():
        raise HTTPException(status_code=400, detail="Account code already exists")
    db.add(models.Account(company_id=company_id, account_code=account_code, account_name=account_name, account_type=account_type, balance=0.0, is_active=True))
    db.commit()
    return RedirectResponse(url="/accounts?success=true", status_code=303)
@app.get("/journal", response_class=HTMLResponse)
def journal_page(request: Request, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    require_company_access(current_emp, 1)
    entries = db.query(models.JournalEntry).order_by(models.JournalEntry.entry_date.desc()).all()
    accounts = db.query(models.Account).filter(models.Account.is_active == True).all()
    accounts_data = [{"id": acc.id, "account_code": acc.account_code, "account_name": acc.account_name} for acc in accounts]
    return templates.TemplateResponse(request, "journal.html", {"active": "journal", "current_emp": current_emp, "entries": entries, "accounts": accounts_data})
@app.post("/api/journal")
def create_journal_entry(description: str = Form(...), reference: str = Form(""), account_ids: List[int] = Form(...), debits: List[float] = Form(...), credits: List[float] = Form(...), line_descriptions: List[str] = Form(...), db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    require_company_access(current_emp, 1)
    if abs(sum(debits) - sum(credits)) > 0.01:
        raise HTTPException(status_code=400, detail=f"Unbalanced entry! Debits ({sum(debits)}) must equal Credits ({sum(credits)}).")

    entry = models.JournalEntry(company_id=company_id, description=description, reference=reference, status="POSTED", created_by=current_emp.id)
    db.add(entry)
    db.flush()

    for acc_id, debit, credit, line_desc in zip(account_ids, debits, credits, line_descriptions):
        if debit > 0 or credit > 0:
            db.add(models.JournalEntryLine(entry_id=entry.id, account_id=acc_id, debit=debit, credit=credit, description=line_desc))
    db.commit()
    return RedirectResponse(url="/journal?success=true", status_code=303)

# --- INVENTORY ---
@app.get("/inventory", response_class=HTMLResponse)
def inventory_page(request: Request, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    require_company_access(current_emp, 1)
    items = db.query(models.InventoryItem).filter(models.InventoryItem.company_id == company_id, models.InventoryItem.is_active == True).all()
    items_data = [{"id": item.id, "item_code": item.item_code, "item_name": item.item_name, "category": item.category, "unit_of_measure": item.unit_of_measure, "current_stock": item.current_stock, "unit_cost": item.unit_cost} for item in items]
    return templates.TemplateResponse(request, "inventory.html", {"active": "inventory", "current_emp": current_emp, "items": items_data})
@app.post("/api/inventory/items")
def create_inventory_item(item_code: str = Form(...), item_name: str = Form(...), category: str = Form(""), unit_of_measure: str = Form("PCS"), unit_cost: float = Form(0.0), db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    require_company_access(current_emp, 1)
    if db.query(models.InventoryItem).filter(models.InventoryItem.item_code == item_code).first():
        raise HTTPException(status_code=400, detail="Item code already exists")
    db.add(models.InventoryItem(company_id=company_id, item_code=item_code, item_name=item_name, category=category, unit_of_measure=unit_of_measure, current_stock=0.0, unit_cost=unit_cost, is_active=True))
    db.commit()
    return RedirectResponse(url="/inventory?success=true", status_code=303)

# --- TASKS ---
@app.get("/tasks", response_class=HTMLResponse)
def tasks_page(request: Request, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    tasks = get_workspace_items(db, current_emp, models.Task, company_id)
    tasks_data = [{"id": t.id, "title": t.title, "description": t.description or "No description provided.", "status": t.status, "priority": t.priority, "assigned_to": t.assigned_employee.name if t.assigned_employee else "Unassigned", "created_at": t.created_at.strftime('%Y-%m-%d')} for t in tasks]
    employees = db.query(models.Employee).filter(models.Employee.is_active == True).all()
    employees_data = [{"id": e.id, "name": e.name, "job_title": e.job_title} for e in employees]
    return templates.TemplateResponse(request, "tasks.html", {"active": "tasks", "current_emp": current_emp, "tasks": tasks_data, "employees": employees_data})


@app.get("/tasks", response_class=HTMLResponse)
def tasks_page(request: Request, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    tasks = get_workspace_items(db, current_emp, models.Task, company_id)
    tasks_data = [{"id": t.id, "title": t.title, "description": t.description or "No description provided.", "status": t.status, "priority": t.priority, "assigned_to": t.assigned_employee.name if t.assigned_employee else "Unassigned", "created_at": t.created_at.strftime('%Y-%m-%d')} for t in tasks]
    employees = db.query(models.Employee).filter(models.Employee.is_active == True).all()
    employees_data = [{"id": e.id, "name": e.name, "job_title": e.job_title} for e in employees]
    return templates.TemplateResponse(request, "tasks.html", {"active": "tasks", "current_emp": current_emp, "tasks": tasks_data, "employees": employees_data})


@app.get("/tasks", response_class=HTMLResponse)
def tasks_page(request: Request, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    tasks = get_workspace_items(db, current_emp, models.Task, company_id)
    tasks_data = [{"id": t.id, "title": t.title, "description": t.description or "No description provided.", "status": t.status, "priority": t.priority, "assigned_to": t.assigned_employee.name if t.assigned_employee else "Unassigned", "created_at": t.created_at.strftime('%Y-%m-%d')} for t in tasks]
    employees = db.query(models.Employee).filter(models.Employee.is_active == True).all()
    employees_data = [{"id": e.id, "name": e.name, "job_title": e.job_title} for e in employees]
    return templates.TemplateResponse(request, "tasks.html", {"active": "tasks", "current_emp": current_emp, "tasks": tasks_data, "employees": employees_data})


@app.post("/api/tasks")
def create_task(title: str = Form(...), description: str = Form(""), assigned_to: int = Form(...), priority: str = Form("MEDIUM"), db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    new_task = models.Task(company_id=company_id, title=title, description=description, assigned_to=assigned_to, created_by=current_emp.id, priority=priority, status="TODO")
    db.add(new_task)
    db.commit()
    db.add(models.TaskActivity(task_id=new_task.id, actor_id=current_emp.id, action="CREATED", new_value=title))
    db.commit()
    return RedirectResponse(url="/tasks?success=true", status_code=303)
@app.post("/api/tasks/{task_id}/status")
def update_task_status(task_id: int, new_status: str = Form(...), db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task: raise HTTPException(status_code=404, detail="Task not found")
    require_company_access(current_emp, task.company_id)
    old_status = task.status
    task.status = new_status
    db.add(models.TaskActivity(task_id=task.id, actor_id=current_emp.id, action="STATUS_CHANGED", previous_value=old_status, new_value=new_status))
    db.commit()
    return RedirectResponse(url="/tasks", status_code=303)

# --- REPORTS ---
@app.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)):
    if current_emp.role != "ADMIN": raise HTTPException(status_code=403, detail="Access denied: Admin role required.")
    companies = db.query(models.Company).all()
    report_data = []
    for comp in companies:
        emp_count = db.query(models.Employee).filter(models.Employee.company_id == comp.id, models.Employee.is_active == True).count()
        active_pos = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.company_id == comp.id, models.PurchaseOrder.status != 'RECEIVED').count()
        inv_value = sum(item.current_stock * item.unit_cost for item in db.query(models.InventoryItem).filter(models.InventoryItem.company_id == comp.id).all())
        journal_count = db.query(models.JournalEntry).filter(models.JournalEntry.company_id == comp.id, models.JournalEntry.status == 'POSTED').count()
        report_data.append({"code": comp.code, "name": comp.name, "employees": emp_count, "active_pos": active_pos, "inventory_value": inv_value, "journal_entries": journal_count})
    
    group_totals = {"employees": sum(r["employees"] for r in report_data), "active_pos": sum(r["active_pos"] for r in report_data), "inventory_value": sum(r["inventory_value"] for r in report_data), "journal_entries": sum(r["journal_entries"] for r in report_data)}
    return templates.TemplateResponse(request, "reports.html", {"active": "reports", "current_emp": current_emp, "report_data": report_data, "group_totals": group_totals})

# --- TENDER ---
@app.get("/tender", response_class=HTMLResponse)
def tender_workspace(request: Request, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    my_tenders = get_workspace_items(db, current_emp, models.Tender, company_id)
    tenders_data = [{"id": t.id, "title": t.title, "client_name": t.client_name, "bid_amount": t.bid_amount, "status": t.status, "created_at": t.created_at.strftime('%Y-%m-%d')} for t in my_tenders]
    return templates.TemplateResponse(request, "tender.html", {"active": "tender", "current_emp": current_emp, "tenders": tenders_data, "user_job": current_emp.job_title or "Employee"})
@app.post("/api/tender")
def create_tender(title: str = Form(...), client_name: str = Form(...), description: str = Form(""), bid_amount: float = Form(0.0), db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    new_tender = models.Tender(company_id=company_id, title=title, client_name=client_name, description=description, bid_amount=bid_amount, status="DRAFT", created_by=current_emp.id, assigned_to=current_emp.id)
    db.add(new_tender)
    db.commit()
    return RedirectResponse(url="/tender?success=true", status_code=303)
@app.post("/api/tender/{tender_id}/status")
def update_tender_status(tender_id: int, new_status: str = Form(...), db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)):
    tender = db.query(models.Tender).filter(models.Tender.id == tender_id, (models.Tender.created_by == current_emp.id) | (models.Tender.assigned_to == current_emp.id)).first()
    if not tender: raise HTTPException(status_code=403, detail="Access denied: This tender is not in your workspace.")
    tender.status = new_status
    db.commit()
    return RedirectResponse(url="/tender", status_code=303)

# --- HEALTH CHECK ---
@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return JSONResponse(content={"status": "healthy", "database": "connected", "message": "Infinity ERP v2 is running smoothly"})
    except Exception as e:
        return JSONResponse(content={"status": "unhealthy", "error": str(e)}, status_code=500)
@app.get("/workspace", response_class=HTMLResponse)
def dynamic_workspace(request: Request, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    job = current_emp.job_title or "Employee"
    my_tasks = get_workspace_items(db, current_emp, models.Task, company_id)
    my_tenders = get_workspace_items(db, current_emp, models.Tender, company_id)
    
    role_data = {"title": "General Workspace", "kpis": [], "form_type": "none"}
    if any(x in job for x in ["CEO", "Vice CEO", "General Manager", "Vice General Manager"]):
        role_data = {"title": "Executive Command Center", "kpis": ["Group Revenue: 12.5M ETB", "Active Tenders: 8", "System Independence: 42 Days"], "form_type": "executive_approval"}
    elif "Bid Manager" in job:
        role_data = {"title": "Bid Management", "kpis": ["Pending Approvals: 3", "Win Rate: 28%", "Active Bids: 5"], "form_type": "bid_approval"}
    elif "Bid Operator" in job:
        role_data = {"title": "Bid Operations", "kpis": ["My Drafts: 2", "Upcoming Deadline: 3 days", "Docs Uploaded: 14"], "form_type": "new_tender_draft"}
    elif "Import Manager" in job:
        role_data = {"title": "Import & Customs", "kpis": ["Active LCs: 2", "Customs Holds: 0", "Pending Landed Costs: 1"], "form_type": "landed_cost_entry"}
    elif "Case Executive" in job:
        role_data = {"title": "Case Management", "kpis": ["Open Cases: 4", "Resolved This Week: 7", "Avg Resolution: 2.1 Days"], "form_type": "new_case"}
    elif "Office Assistant" in job:
        role_data = {"title": "Administrative Support", "kpis": ["Documents Scanned: 45", "Supply Requests: 2", "Meetings Scheduled: 3"], "form_type": "doc_upload"}
    elif "Finance Manager" in job:
        role_data = {"title": "Financial Control", "kpis": ["Pending Payment Approvals: 5", "Cash Flow: Healthy", "Unreconciled: 0"], "form_type": "payment_approval"}
    elif "Accountant" in job:
        role_data = {"title": "Accounting Desk", "kpis": ["Pending Journals: 3", "Invoices Processed: 28", "Bank Recs: Up to Date"], "form_type": "journal_entry"}
    elif "Legal Counsel" in job:
        role_data = {"title": "Legal & Compliance", "kpis": ["Contracts Pending Review: 2", "Compliance Alerts: 0", "Active Disputes: 0"], "form_type": "legal_note"}
    elif "HR" in job:
        role_data = {"title": "Human Resources", "kpis": ["Pending Leave Requests: 3", "Password Resets: 1", "Onboarding: 0"], "form_type": "hr_onboarding"}
    elif "ICT Coordinator" in job:
        role_data = {"title": "IT Administration", "kpis": ["System Health: Optimal", "Last Backup: Today", "Active Sessions: " + str(db.query(models.Employee).filter(models.Employee.is_active==True).count())], "form_type": "user_access"}

    ws_tasks_data = []
    for t in my_tasks:
        ws_tasks_data.append({
            "id": t.id, "title": t.title, "description": t.description or "No description provided.",
            "status": t.status, "priority": t.priority,
            "assigned_to": t.assigned_employee.name if t.assigned_employee else "Unassigned",
            "responses": [{"status": r.status, "comment": r.comment or "No comment", "created_at": r.created_at.strftime('%Y-%m-%d %H:%M')} for r in t.responses]
        })
    
    return templates.TemplateResponse(request, "workspace.html", {
        "active": "workspace", "current_emp": current_emp, "job_title": job, 
        "role_data": role_data, "tasks": my_tasks, "tenders": my_tenders, "task_data_json": json.dumps(ws_tasks_data)
    })


@app.get("/suppliers", response_class=HTMLResponse)
def suppliers_page(request: Request, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    require_company_access(current_emp, 1)
    suppliers = db.query(models.Supplier).filter(models.Supplier.company_id == company_id, models.Supplier.is_active == True).all()
    return templates.TemplateResponse(request, "suppliers.html", {"active": "suppliers", "current_emp": current_emp, "suppliers": suppliers})
@app.post("/api/suppliers")
def create_supplier(
    name: str = Form(...), contact_person: str = Form(""), email: str = Form(""), 
    phone: str = Form(""), country: str = Form(""), tax_id: str = Form(""), rating: int = Form(3),
    db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)
):
    require_company_access(current_emp, 1)
    db.add(models.Supplier(
        company_id=1, name=name, contact_person=contact_person, email=email, 
        phone=phone, country=country, tax_id=tax_id, rating=rating, is_active=True
    ))
    db.commit()
    return RedirectResponse(url="/suppliers?success=true", status_code=303)
@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(...),
    reference_type: str = Form(...),
    reference_id: int = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
    current_emp: models.Employee = Depends(get_current_employee)
):
    # Save file securely
    filename = f"{int(datetime.utcnow().timestamp())}_{file.filename.replace(' ', '_')}"
    filepath = os.path.join("uploads", filename)
    
    with open(filepath, "wb") as buffer:
        buffer.write(await file.read())
        
    db.add(models.Document(
        company_id=current_emp.company_id,
        filename=file.filename,
        filepath=filepath,
        file_type=file.content_type,
        reference_type=reference_type,
        reference_id=reference_id,
        uploaded_by=current_emp.id,
        description=description
    ))
    db.commit()
    return RedirectResponse(url=f"/documents?ref_type={reference_type}&ref_id={reference_id}&success=true", status_code=303)
@app.get("/documents", response_class=HTMLResponse)
def documents_page(request: Request, ref_type: str = "", ref_id: int = 0, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)):
    docs = db.query(models.Document).filter(
        models.Document.reference_type == ref_type,
        models.Document.reference_id == ref_id
    ).order_by(models.Document.uploaded_at.desc()).all()
    return templates.TemplateResponse(request, "documents.html", {"active": "documents", "current_emp": current_emp, "docs": docs, "ref_type": ref_type, "ref_id": ref_id})
@app.get("/api/download/{doc_id}")
def download_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc or not os.path.exists(doc.filepath):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(doc.filepath, filename=doc.filename, media_type=doc.file_type)
@app.get("/landed-costs", response_class=HTMLResponse)
def landed_costs_page(request: Request, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    require_company_access(current_emp, 1)
    # Get POs for this company to filter receipts correctly
    pos = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.company_id == company_id).all()
    po_ids = [p.id for p in pos]
    receipts = db.query(models.Receipt).filter(models.Receipt.po_id.in_(po_ids)).order_by(models.Receipt.received_at.desc()).all() if po_ids else []
    costs = db.query(models.LandedCost).filter(models.LandedCost.company_id == company_id).order_by(models.LandedCost.date.desc()).all()
    return templates.TemplateResponse(request, "landed_costs.html", {"active": "landed_costs", "current_emp": current_emp, "receipts": receipts, "costs": costs})
@app.post("/api/landed-costs")
def add_landed_cost(
    receipt_id: int = Form(...), cost_type: str = Form(...), amount: float = Form(...),
    currency: str = Form("ETB"), notes: str = Form(""),
    db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)
):
    require_company_access(current_emp, 1)
    db.add(models.LandedCost(
        company_id=1, receipt_id=receipt_id, cost_type=cost_type, 
        amount=amount, currency=currency, notes=notes
    ))
    db.commit()
    return RedirectResponse(url="/landed-costs?success=true", status_code=303)
@app.post("/api/tender/{tender_id}/convert-to-po")
def convert_tender_to_po(
    tender_id: int,
    db: Session = Depends(get_db),
    current_emp: models.Employee = Depends(get_current_employee)
):
    tender = db.query(models.Tender).filter(models.Tender.id == tender_id).first()
    if not tender: raise HTTPException(status_code=404, detail="Tender not found")
    
    # Check if already converted
    existing_po = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.tender_id == tender_id).first()
    if existing_po:
        return RedirectResponse(url=f"/receiving?msg=PO already exists: {existing_po.po_number}", status_code=303)

    # Generate new PO number
    po_count = db.query(models.PurchaseOrder).count() + 1
    new_po_number = f"PO-2026-{po_count:03d}"

    new_po = models.PurchaseOrder(
        po_number=new_po_number,
        company_id=tender.company_id,
        status="ISSUED",
        tender_id=tender.id
    )
    db.add(new_po)
    db.commit()
    
    # Update tender status
    tender.status = "WON"
    db.commit()
    
    return RedirectResponse(url=f"/receiving?msg=Converted Tender to {new_po_number}", status_code=303)
@app.get("/customers", response_class=HTMLResponse)
def customers_page(request: Request, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    require_company_access(current_emp, 1)
    customers = db.query(models.Customer).filter(models.Customer.company_id == company_id, models.Customer.is_active == True).all()
    return templates.TemplateResponse(request, "customers.html", {"active": "customers", "current_emp": current_emp, "customers": customers})
@app.post("/api/customers")
def create_customer(
    name: str = Form(...), contact_person: str = Form(""), phone: str = Form(""), 
    email: str = Form(""), tin: str = Form(""),
    db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)
):
    require_company_access(current_emp, 1)
    db.add(models.Customer(company_id=company_id, name=name, contact_person=contact_person, phone=phone, email=email, tin=tin, is_active=True))
    db.commit()
    return RedirectResponse(url="/customers?success=true", status_code=303)
@app.get("/invoices", response_class=HTMLResponse)
def invoices_page(request: Request, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    require_company_access(current_emp, 1)
    invoices = db.query(models.Invoice).order_by(models.Invoice.issue_date.desc()).all()
    customers = db.query(models.Customer).filter(models.Customer.company_id == company_id).all()
    sales_orders = db.query(models.SalesOrder).filter(models.SalesOrder.status != "INVOICED").all()
    return templates.TemplateResponse(request, "invoices.html", {"active": "invoices", "current_emp": current_emp, "invoices": invoices, "customers": customers, "sales_orders": sales_orders})
@app.post("/api/invoices")
def create_invoice(
    sales_order_id: int = Form(...), invoice_number: str = Form(...), due_date: str = Form(""),
    db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)
):
    require_company_access(current_emp, 1)
    so = db.query(models.SalesOrder).filter(models.SalesOrder.id == sales_order_id).first()
    if not so: raise HTTPException(status_code=400, detail="Sales Order not found")
    
    # Check if already invoiced
    if db.query(models.Invoice).filter(models.Invoice.invoice_number == invoice_number).first():
        raise HTTPException(status_code=400, detail="Invoice number already exists")

    inv = models.Invoice(
        company_id=1, sales_order_id=so.id, invoice_number=invoice_number, 
        customer_id=so.customer_id, total_amount=so.total_amount, status="UNPAID"
    )
    if due_date:
        inv.due_date = datetime.strptime(due_date, "%Y-%m-%d")
        
    db.add(inv)
    so.status = "INVOICED"
    db.commit()
    return RedirectResponse(url="/invoices?success=true", status_code=303)
@app.post("/api/invoices/{inv_id}/mark-paid")
def mark_invoice_paid(inv_id: int, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)):
    inv = db.query(models.Invoice).filter(models.Invoice.id == inv_id).first()
    if not inv: raise HTTPException(status_code=404, detail="Invoice not found")
    inv.status = "PAID"
    db.commit()
    return RedirectResponse(url="/invoices", status_code=303)

import secrets
@app.get("/request-reset", response_class=HTMLResponse)
def request_reset_page(request: Request):
    return templates.TemplateResponse(request, "request_reset.html", {"error": None, "success": None})
@app.post("/api/request-reset")
def request_password_reset(request: Request, username: str = Form(...), db: Session = Depends(get_db)):
    emp = db.query(models.Employee).filter(models.Employee.username == username, models.Employee.is_active == True).first()
    if not emp:
        # Don't reveal if user exists for security
        return templates.TemplateResponse(request, "request_reset.html", {"error": "If the username exists, a reset request has been sent to the Admin.", "success": None})
    
    emp.password_reset_requested = True
    emp.reset_token = secrets.token_hex(16)
    db.commit()
    return templates.TemplateResponse(request, "request_reset.html", {"error": None, "success": "Reset request sent to Admin. You will be notified when approved."})
@app.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request, token: str = ""):
    return templates.TemplateResponse(request, "reset_password.html", {"token": token, "error": None, "success": None})
@app.post("/api/reset-password")
def process_reset_password(request: Request, token: str = Form(...), new_password: str = Form(...), confirm_password: str = Form(...), db: Session = Depends(get_db)):
    if new_password != confirm_password:
        return templates.TemplateResponse(request, "reset_password.html", {"token": token, "error": "Passwords do not match.", "success": None})
    
    emp = db.query(models.Employee).filter(models.Employee.reset_token == token, models.Employee.password_reset_requested == True).first()
    if not emp:
        return templates.TemplateResponse(request, "reset_password.html", {"token": token, "error": "Invalid or expired token.", "success": None})
    
    emp.password_hash = get_password_hash(new_password)
    emp.password_reset_requested = False
    emp.reset_token = None
    db.commit()
    return templates.TemplateResponse(request, "reset_password.html", {"token": token, "error": None, "success": "Password successfully changed! You can now log in."})
@app.post("/api/admin/approve-reset/{emp_id}")
def admin_approve_reset(emp_id: int, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)):
    if current_emp.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    emp.password_reset_requested = False
    # Generate a fresh token for the employee to use
    emp.reset_token = secrets.token_hex(16)
    db.commit()
    return RedirectResponse(url="/employees?msg=Reset approved. Share this token with the employee: " + emp.reset_token, status_code=303)
@app.get("/executive", response_class=HTMLResponse)
def executive_dashboard(request: Request, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    if "CEO" not in current_emp.job_title and "Vice CEO" not in current_emp.job_title and "General Manager" not in current_emp.job_title:
        raise HTTPException(status_code=403, detail="Executive access required")
    
    petty_cashes = db.query(models.PettyCash).filter(models.PettyCash.company_id == company_id).order_by(models.PettyCash.created_at.desc()).all()
    legal_memos = db.query(models.LegalMemo).filter(models.LegalMemo.company_id == company_id).order_by(models.LegalMemo.created_at.desc()).all()
    bonds = db.query(models.FinancialBond).filter(models.FinancialBond.company_id == company_id).order_by(models.FinancialBond.created_at.desc()).all()
    
    total_tenders = db.query(models.Tender).filter(models.Tender.company_id == company_id).count()
    won_tenders = db.query(models.Tender).filter(models.Tender.company_id == company_id, models.Tender.status == "WON").count()
    win_rate = round((won_tenders / total_tenders * 100), 1) if total_tenders > 0 else 0.0
    recent_tenders = db.query(models.Tender).filter(models.Tender.company_id == company_id).order_by(models.Tender.created_at.desc()).limit(5).all()
    
    tasks = get_workspace_items(db, current_emp, models.Task, company_id)
    posted_journals_count = db.query(models.JournalEntry).filter(models.JournalEntry.company_id == company_id, models.JournalEntry.status == "POSTED").count()

    total_tasks = db.query(models.Task).filter(models.Task.company_id == company_id).count()
    weekly_ongoing = db.query(models.Task).filter(
        models.Task.company_id == company_id,
        models.Task.status != 'DONE',
        models.Task.created_at >= datetime.utcnow() - timedelta(days=7)
    ).order_by(models.Task.created_at.desc()).all()
    
    all_tasks_data = []
    for t in tasks:
        all_tasks_data.append({
            "id": t.id, "title": t.title, "description": t.description or "No description provided.",
            "status": t.status, "priority": t.priority,
            "assigned_to": t.assigned_employee.name if t.assigned_employee else "Unassigned",
            "responses": [{"status": r.status, "comment": r.comment or "No comment", "created_at": r.created_at.strftime('%Y-%m-%d %H:%M')} for r in t.responses]
        })
    
    employees = db.query(models.Employee).filter(models.Employee.is_active == True).all()
    pending_approvals = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.company_id == company_id, models.ApprovalRequest.status == "PENDING").all()

    return templates.TemplateResponse(request, "executive.html", {
        "active": "executive", "current_emp": current_emp, "petty_cashes": petty_cashes, "legal_memos": legal_memos, "bonds": bonds,
        "win_rate": win_rate, "recent_tenders": recent_tenders, "tasks": tasks, "posted_journals_count": posted_journals_count, 
        "employees": employees, "pending_approvals": pending_approvals, "total_tasks": total_tasks, "weekly_ongoing": weekly_ongoing, 
        "task_data_json": json.dumps(all_tasks_data)
    })


@app.post("/api/executive/approve-petty-cash/{item_id}")
def approve_petty_cash(item_id: int, action: str = Form(...), db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)):
    if "CEO" not in current_emp.job_title and "Vice CEO" not in current_emp.job_title:
        raise HTTPException(status_code=403, detail="Executive access required")
    item = db.query(models.PettyCash).filter(models.PettyCash.id == item_id).first()
    if item:
        item.status = action # APPROVED or REJECTED
        item.approved_by = current_emp.id
        db.commit()
    return RedirectResponse(url="/executive", status_code=303)
@app.post("/api/executive/approve-salary/{item_id}")
def approve_salary(item_id: int, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)):
    req = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == item_id).first()
    if req:
        req.status = "APPROVED"
        req.approved_by = current_emp.id
        db.commit()
    return RedirectResponse(url="/executive?msg=Salary Payment Approved", status_code=303)
@app.post("/api/executive/approve-voucher/{item_id}")
def approve_voucher(item_id: int, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)):
    req = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == item_id).first()
    if req:
        req.status = "APPROVED"
        req.approved_by = current_emp.id
        db.commit()
    return RedirectResponse(url="/executive?msg=Payment Voucher Approved", status_code=303)
@app.post("/api/executive/assign-task")
def executive_assign_task(title: str = Form(...), description: str = Form(""), assigned_to: int = Form(...), priority: str = Form("HIGH"), db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    new_task = models.Task(company_id=company_id, title=title, description=description, assigned_to=assigned_to, created_by=current_emp.id, priority=priority, status="TODO")
    db.add(new_task)
    db.commit()
    db.add(models.TaskActivity(task_id=new_task.id, actor_id=current_emp.id, action="ASSIGNED_BY_EXECUTIVE", new_value=title))
    db.commit()
        # Send Telegram Notification to Assigned Employee
    assigned_emp = db.query(models.Employee).filter(models.Employee.id == assigned_to).first()
    if assigned_emp and assigned_emp.telegram_id:
        notify_employee(assigned_to, f"📌 <b>New Task Assigned</b>\n\n <b>{title}</b>\n📋 Priority: {priority}\n\nPlease check your ERP Workspace to view details and report progress.")
    
    return RedirectResponse(url="/executive?msg=Task Assigned Successfully", status_code=303)

import os
import mimetypes

# Helper to check if user can access a category
def can_access_category(current_emp: models.Employee, allowed_roles_str: str) -> bool:
    if not current_emp or not allowed_roles_str:
        return False
    # System ADMINS can see all categories
    if current_emp.role == "ADMIN":
        return True
    user_role = current_emp.job_title
    allowed_roles = [r.strip() for r in allowed_roles_str.split(",")]
    # Check for exact match
    if user_role in allowed_roles:
        return True
    return False
    user_role = current_emp.job_title
    allowed_roles = [r.strip() for r in allowed_roles_str.split(",")]
    # Check for exact match or if user is a super admin
    if user_role in allowed_roles or "CEO" in user_role or "Vice CEO" in user_role:
        return True
    return False
@app.get("/document-library", response_class=HTMLResponse)
def document_library(request: Request, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    # Get categories the user is allowed to see
    all_categories = db.query(models.DocumentCategory).all()
    allowed_categories = [c for c in all_categories if can_access_category(current_emp, c.allowed_roles)]
    allowed_cat_ids = [c.id for c in allowed_categories]
    
    # Fetch documents (non-archived, belonging to allowed categories)
    # Filter documents by company, unless user is CEO/Vice CEO (Group View)
    if "CEO" in current_emp.job_title or "Vice CEO" in current_emp.job_title:
        docs = db.query(models.Document).filter(
            models.Document.category_id.in_(allowed_cat_ids),
            models.Document.is_archived == False
        ).order_by(models.Document.uploaded_at.desc()).all()
    else:
        docs = db.query(models.Document).filter(
        models.Document.company_id == current_emp.company_id,
        models.Document.category_id.in_(allowed_cat_ids),
        models.Document.is_archived == False
    ).order_by(models.Document.uploaded_at.desc()).all()
    
    return templates.TemplateResponse(request, "document_library.html", {
        "active": "document_library", "current_emp": current_emp,
        "categories": allowed_categories, "documents": docs
    })
@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    category_id: int = Form(...),
    reference_type: str = Form(""),
    reference_id: int = Form(0),
    description: str = Form(""),
    db: Session = Depends(get_db),
    current_emp: models.Employee = Depends(get_current_employee)
):
    # Verify category access
    cat = db.query(models.DocumentCategory).filter(models.DocumentCategory.id == category_id).first()
    if not cat or not can_access_category(current_emp, cat.allowed_roles):
        raise HTTPException(status_code=403, detail="Access denied to this category")
    
    # Check file type
    allowed_ext = ['.pdf', '.docx', '.xlsx', '.jpg', '.png', '.jpeg']
    _, ext = os.path.splitext(file.filename)
    if ext.lower() not in allowed_ext:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed: {', '.join(allowed_ext)}")
    
    # Create upload directory
    upload_dir = "uploads/documents"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Handle versioning: check if file with same name exists in same category/ref
    existing_doc = db.query(models.Document).filter(
        models.Document.filename == file.filename,
        models.Document.category_id == category_id,
        models.Document.reference_type == reference_type,
        models.Document.reference_id == reference_id,
        models.Document.is_archived == False
    ).first()
    
    version = 1
    if existing_doc:
        version = existing_doc.version + 1
        existing_doc.is_archived = True # Archive old version
        db.commit()
    
    # Save file
    safe_filename = f"{int(datetime.utcnow().timestamp())}_{version}_{file.filename.replace(' ', '_')}"
    filepath = os.path.join(upload_dir, safe_filename)
    
    file_content = await file.read()
    file_size_kb = len(file_content) // 1024
    
    with open(filepath, "wb") as buffer:
        buffer.write(file_content)
        
    # Save to DB
    new_doc = models.Document(
        company_id=current_emp.company_id,
        category_id=category_id,
        filename=file.filename,
        filepath=filepath,
        file_type=file.content_type or mimetypes.guess_type(file.filename)[0],
        reference_type=reference_type if reference_type else None,
        reference_id=reference_id if reference_id > 0 else None,
        uploaded_by=current_emp.id,
        description=description,
        version=version,
        file_size=file_size_kb,
        is_archived=False
    )
    db.add(new_doc)
    db.commit()
    
    return RedirectResponse(url="/document-library?success=true", status_code=303)
@app.get("/api/documents/download/{doc_id}")
def download_document(doc_id: int, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)):
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc or not os.path.exists(doc.filepath):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Security check: can this user access this category?
    cat = db.query(models.DocumentCategory).filter(models.DocumentCategory.id == doc.category_id).first()
    if cat and not can_access_category(current_emp, cat.allowed_roles):
        raise HTTPException(status_code=403, detail="Access denied")
        
    return FileResponse(doc.filepath, filename=doc.filename, media_type=doc.file_type)
@app.post("/api/tasks/update/{task_id}")
def update_task_status(task_id: int, status: str = Form(...), comment: str = Form(""), db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task:
        old_status = task.status
        task.status = status
        db.commit()
        # Log the response
        db.add(models.TaskResponse(task_id=task_id, employee_id=current_emp.id, status=status, comment=comment))
        db.add(models.TaskActivity(task_id=task_id, actor_id=current_emp.id, action="STATUS_UPDATE", previous_value=old_status, new_value=status))
        db.commit()
        # Send Telegram Notification to CEO/GM
    if status in ["BLOCKED", "DONE"]:
        emoji = "🚨" if status == "BLOCKED" else "✅"
        notify_ceo(f"{emoji} <b>Task Update: {status}</b>\n\n <b>{task.title}</b>\n💬 Comment: {comment}\n By: {current_emp.name}")
        
    return RedirectResponse(url="/workspace?msg=Task updated successfully", status_code=303)
@app.post("/api/tasks/resend/{task_id}")
def resend_task(task_id: int, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task:
        task.status = "TODO"
        db.commit()
        db.add(models.TaskActivity(task_id=task_id, actor_id=current_emp.id, action="RESENT_BY_EXECUTIVE", new_value="Reset to TODO"))
        db.commit()
    return RedirectResponse(url="/executive?msg=Task resent to employee", status_code=303)

@app.get("/compliance", response_class=HTMLResponse)
def compliance_calendar(request: Request, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    items = db.query(models.ComplianceItem).filter(models.ComplianceItem.company_id == company_id).order_by(models.ComplianceItem.expiry_date.asc()).all()
    
    today = datetime.utcnow()
    alerts_triggered = []
    
    for item in items:
        days_left = (item.expiry_date - today).days
        
        # Update Status
        if days_left < 0:
            item.status = "EXPIRED"
        elif days_left <= 15:
            item.status = "CRITICAL"
        elif days_left <= 30:
            item.status = "WARNING"
        else:
            item.status = "VALID"
            
        # Trigger Telegram Alerts (Only once per threshold)
        if days_left == 30 and not item.alert_30_sent:
            msg = f"⚠️ <b>Compliance Alert (30 Days)</b>\n\n <b>{item.name}</b> expires in 30 days.\n Owner: {item.owner_role}\n\nPlease initiate renewal process per SOP-006."
            alerts_triggered.append(msg)
            item.alert_30_sent = True
        elif days_left == 15 and not item.alert_15_sent:
            msg = f"🚨 <b>Compliance Alert (15 Days)</b>\n\n <b>{item.name}</b> expires in 15 days!\n Owner: {item.owner_role}\n\nUrgent action required."
            alerts_triggered.append(msg)
            item.alert_15_sent = True
        elif days_left == 3 and not item.alert_3_sent:
            msg = f"🔴 <b>CRITICAL: {item.name} expires in 3 DAYS!</b>\n\nImmediate action required by {item.owner_role}."
            alerts_triggered.append(msg)
            item.alert_3_sent = True
            
    if alerts_triggered:
        db.commit()
        config_path = 'telegram_config.json'
        if os.path.exists(config_path):
            import json
            with open(config_path, 'r') as cf:
                config = json.load(cf)
            token = config.get('bot_token')
            admin_id = config.get('admin_chat_id')
            if token and admin_id:
                for alert in alerts_triggered:
                    # Reuse existing send logic
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    payload = json.dumps({"chat_id": admin_id, "text": alert, "parse_mode": "HTML"}).encode('utf-8')
                    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
                    try:
                        urllib.request.urlopen(req)
                    except: pass

    days_map = {item.id: max(0, (item.expiry_date - datetime.utcnow()).days) for item in items}
    return templates.TemplateResponse(request, "compliance.html", {
        "active": "compliance", "current_emp": current_emp, "items": items, "days_map": days_map, "now": datetime.utcnow()
    })


# --- KPI DASHBOARD ROUTE ---
@app.get("/kpi-dashboard", response_class=HTMLResponse)
def kpi_dashboard(request: Request, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    # Calculate Live KPIs
    total_tenders = db.query(models.Tender).filter(models.Tender.company_id == company_id).count()
    won_tenders = db.query(models.Tender).filter(models.Tender.company_id == company_id, models.Tender.status == "WON").count()
    win_rate = round((won_tenders / total_tenders * 100), 1) if total_tenders > 0 else 0.0
    
    total_licenses = db.query(models.ComplianceItem).filter(models.ComplianceItem.company_id == company_id).count()
    valid_licenses = db.query(models.ComplianceItem).filter(models.ComplianceItem.company_id == company_id, models.ComplianceItem.status == "VALID").count()
    license_validity = round((valid_licenses / total_licenses * 100), 1) if total_licenses > 0 else 100.0

    # Active Workflows
    active_workflows = db.query(models.Workflow).filter(models.Workflow.company_id == company_id, models.Workflow.status == "IN_PROGRESS").order_by(models.Workflow.created_at.desc()).all()
    
    # Get steps for active workflows
    workflow_data = []
    for wf in active_workflows:
        steps = db.query(models.WorkflowStep).filter(models.WorkflowStep.workflow_id == wf.id).order_by(models.WorkflowStep.step_number).all()
        workflow_data.append({"wf": wf, "steps": steps})

    return templates.TemplateResponse(request, "kpi_dashboard.html", {
        "active": "kpi_dashboard", "current_emp": current_emp,
        "win_rate": win_rate, "license_validity": license_validity,
        "workflows": workflow_data
    })

# --- SOP WORKFLOW ROUTES ---
@app.post("/api/sop/start")
def start_sop(sop_code: str = Form(...), reference_id: str = Form(""), db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    sop_names = {
        "SOP-001": "Tender Opportunity Assessment",
        "SOP-006": "License Renewal Management",
        "SOP-007": "Document Receipt and Filing"
    }
    
    wf = models.Workflow(company_id=company_id, sop_code=sop_code, sop_name=sop_names.get(sop_code, sop_code), reference_id=reference_id, created_by=current_emp.id)
    db.add(wf)
    db.flush()
    
    # Define Steps based on Manual
    steps_def = []
    if sop_code == "SOP-001":
        steps_def = [
            (1, "Monitor & Purchase Document", "Bid Operator"),
            (2, "Create Tender Summary Sheet", "Bid Operator"),
            (3, "Feasibility Analysis", "Bid Manager"),
            (4, "Go/No-Go Decision", "General Manager")
        ]
    elif sop_code == "SOP-006":
        steps_def = [
            (1, "Identify Expiring License", "HR & Administrator"),
            (2, "Initiate Renewal Process", "HR & Administrator"),
            (3, "Physical Submission", "Liaison Officer"),
            (4, "Update Master Calendar", "HR & Administrator")
        ]
    else:
        steps_def = [(1, "Initial Step", "Office Assistant"), (2, "Final Step", "HR & Administrator")]
        
    for num, name, role in steps_def:
        db.add(models.WorkflowStep(workflow_id=wf.id, step_number=num, step_name=name, assigned_role=role))
        
    db.commit()
    return RedirectResponse(url="/kpi-dashboard?msg=SOP+Workflow+Started", status_code=303)

@app.post("/api/sop/advance/{step_id}")
def advance_sop_step(step_id: int, notes: str = Form(""), db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)):
    step = db.query(models.WorkflowStep).filter(models.WorkflowStep.id == step_id).first()
    if step and step.status == "PENDING":
        step.status = "DONE"
        step.notes = notes
        step.completed_at = datetime.utcnow()
        db.commit()
        
        # Check if workflow is complete
        wf = db.query(models.Workflow).filter(models.Workflow.id == step.workflow_id).first()
        remaining = db.query(models.WorkflowStep).filter(models.WorkflowStep.workflow_id == wf.id, models.WorkflowStep.status == "PENDING").count()
        if remaining == 0:
            wf.status = "COMPLETED"
            db.commit()
            
    return RedirectResponse(url="/kpi-dashboard", status_code=303)


@app.get("/document-registers", response_class=HTMLResponse)
def document_registers(request: Request, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    incoming_docs = db.query(models.IncomingDocument).filter(models.IncomingDocument.company_id == company_id).order_by(models.IncomingDocument.received_date.desc()).all()
    movements = db.query(models.DocumentMovement).filter(models.DocumentMovement.company_id == company_id).order_by(models.DocumentMovement.date_out.desc()).all()
    checklists = db.query(models.DailyFilingChecklist).filter(models.DailyFilingChecklist.company_id == company_id).order_by(models.DailyFilingChecklist.checklist_date.desc()).limit(7).all()
    
    # Get employee names for checklists
    emp_names = {e.id: e.name for e in db.query(models.Employee).all()}
    
    return templates.TemplateResponse(request, "document_registers.html", {
        "active": "document_registers", "current_emp": current_emp,
        "incoming_docs": incoming_docs, "movements": movements, "checklists": checklists, "emp_names": emp_names
    })

@app.post("/api/registers/log-incoming")
def log_incoming(sender: str = Form(...), description: str = Form(...), department: str = Form(...), db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)):
    import random
    temp_num = f"TEMP-{datetime.utcnow().strftime('%Y')}-{random.randint(1000, 9999)}"
    db.add(models.IncomingDocument(company_id=company_id, sender=sender, description=description, temp_doc_number=temp_num, department=department))
    db.commit()
    return RedirectResponse(url="/document-registers?tab=incoming&msg=Document+Logged", status_code=303)

@app.post("/api/registers/check-in/{movement_id}")
def check_in_doc(movement_id: int, db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee)):
    mov = db.query(models.DocumentMovement).filter(models.DocumentMovement.id == movement_id).first()
    if mov:
        mov.status = "RETURNED"
        mov.date_in = datetime.utcnow()
        db.commit()
    return RedirectResponse(url="/document-registers?tab=movement&msg=Document+Checked+In", status_code=303)

@app.post("/api/registers/submit-checklist")
def submit_checklist(
    all_logged: str = Form("off"), all_scanned: str = Form("off"), all_filed: str = Form("off"),
    index_updated: str = Form("off"), cabinets_locked: str = Form("off"), supplies_checked: str = Form("off"),
    db: Session = Depends(get_db), current_emp: models.Employee = Depends(get_current_employee), company_id: int = Depends(get_current_company_id)
):
    db.add(models.DailyFilingChecklist(
        company_id=company_id, completed_by=current_emp.id,
        all_logged=(all_logged == "on"), all_scanned=(all_scanned == "on"), all_filed=(all_filed == "on"),
        index_updated=(index_updated == "on"), cabinets_locked=(cabinets_locked == "on"), supplies_checked=(supplies_checked == "on"), is_signed=True
    ))
    db.commit()
    return RedirectResponse(url="/document-registers?tab=checklist&msg=Daily+Checklist+Signed+and+Submitted", status_code=303)
