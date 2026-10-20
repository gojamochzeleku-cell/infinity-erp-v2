from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)
    name = Column(String)
    employees = relationship("Employee", back_populates="company")

class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    username = Column(String, unique=True, nullable=True)
    password_hash = Column(String, nullable=True)
    job_title = Column(String, nullable=True)
    telegram_id = Column(String, unique=True, nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    role = Column(String, default="VIEWER")
    created_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    password_reset_requested = Column(Boolean, default=False)
    reset_token = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    language = Column(String, default="en")
    company = relationship("Company", back_populates="employees")

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id = Column(Integer, primary_key=True, index=True)
    po_number = Column(String, unique=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    tender_id = Column(Integer, ForeignKey("tenders.id"), nullable=True)
    status = Column(String, default="ISSUED")
    lines = relationship("POLine", back_populates="po")

class POLine(Base):
    __tablename__ = "po_lines"
    id = Column(Integer, primary_key=True, index=True)
    po_id = Column(Integer, ForeignKey("purchase_orders.id"))
    item_name = Column(String)
    ordered_qty = Column(Float)
    received_qty = Column(Float, default=0)
    po = relationship("PurchaseOrder", back_populates="lines")

class Receipt(Base):
    __tablename__ = "receipts"
    id = Column(Integer, primary_key=True, index=True)
    receipt_number = Column(String, unique=True)
    po_id = Column(Integer, ForeignKey("purchase_orders.id"))
    received_by = Column(Integer, ForeignKey("employees.id"))
    received_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(String, nullable=True)
    lines = relationship("ReceiptLine", back_populates="receipt")

class ReceiptLine(Base):
    __tablename__ = "receipt_lines"
    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id"))
    po_line_id = Column(Integer, ForeignKey("po_lines.id"))
    received_qty = Column(Float)
    receipt = relationship("Receipt", back_populates="lines")

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    account_code = Column(String, unique=True, index=True)
    account_name = Column(String)
    account_type = Column(String)
    balance = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)

class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    entry_date = Column(DateTime, default=datetime.utcnow)
    description = Column(String)
    reference = Column(String, nullable=True)
    status = Column(String, default="DRAFT")
    created_by = Column(Integer, ForeignKey("employees.id"))
    lines = relationship("JournalEntryLine", back_populates="entry")

class JournalEntryLine(Base):
    __tablename__ = "journal_entry_lines"
    id = Column(Integer, primary_key=True, index=True)
    entry_id = Column(Integer, ForeignKey("journal_entries.id"))
    account_id = Column(Integer, ForeignKey("accounts.id"))
    debit = Column(Float, default=0.0)
    credit = Column(Float, default=0.0)
    description = Column(String, nullable=True)
    entry = relationship("JournalEntry", back_populates="lines")

class Warehouse(Base):
    __tablename__ = "warehouses"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    name = Column(String)
    location = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    item_code = Column(String, unique=True, index=True)
    item_name = Column(String)
    category = Column(String, nullable=True)
    unit_of_measure = Column(String, default="PCS")
    current_stock = Column(Float, default=0.0)
    unit_cost = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)

class StockMovement(Base):
    __tablename__ = "stock_movements"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    item_id = Column(Integer, ForeignKey("inventory_items.id"))
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"))
    movement_type = Column(String)
    quantity = Column(Float)
    reference_type = Column(String, nullable=True)
    reference_id = Column(Integer, nullable=True)
    movement_date = Column(DateTime, default=datetime.utcnow)
    notes = Column(String, nullable=True)

class TaskActivity(Base):
    __tablename__ = "task_activities"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    actor_id = Column(Integer, ForeignKey("employees.id"))
    action = Column(String)
    previous_value = Column(String, nullable=True)
    new_value = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Tender(Base):
    __tablename__ = "tenders"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    title = Column(String)
    client_name = Column(String)
    description = Column(String, nullable=True)
    bid_amount = Column(Float, default=0.0)
    status = Column(String, default="DRAFT")
    created_by = Column(Integer, ForeignKey("employees.id"))
    assigned_to = Column(Integer, ForeignKey("employees.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    name = Column(String)
    contact_person = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    country = Column(String, nullable=True)
    tax_id = Column(String, nullable=True)
    rating = Column(Integer, default=3)
    is_active = Column(Boolean, default=True)

class DocumentCategory(Base):
    __tablename__ = "document_categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    description = Column(String, nullable=True)
    allowed_roles = Column(String)
    documents = relationship("Document", back_populates="category")

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    category_id = Column(Integer, ForeignKey("document_categories.id"), nullable=True)
    filename = Column(String)
    filepath = Column(String)
    file_type = Column(String, nullable=True)
    reference_type = Column(String, nullable=True)
    reference_id = Column(Integer, nullable=True)
    uploaded_by = Column(Integer, ForeignKey("employees.id"))
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    description = Column(String, nullable=True)
    version = Column(Integer, default=1)
    file_size = Column(Integer, default=0)
    is_archived = Column(Boolean, default=False)
    doc_type_code = Column(String, nullable=True)
    project_id = Column(String, nullable=True)
    access_level = Column(Integer, default=1)
    retention_years = Column(Integer, default=3)
    status = Column(String, default="ACTIVE")
    category = relationship("DocumentCategory", back_populates="documents")

class LandedCost(Base):
    __tablename__ = "landed_costs"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    receipt_id = Column(Integer, ForeignKey("receipts.id"))
    cost_type = Column(String)
    amount = Column(Float)
    currency = Column(String, default="ETB")
    date = Column(DateTime, default=datetime.utcnow)
    notes = Column(String, nullable=True)

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    name = Column(String)
    contact_person = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    tin = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

class SalesOrder(Base):
    __tablename__ = "sales_orders"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    customer_id = Column(Integer, ForeignKey("customers.id"))
    order_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="DRAFT")
    total_amount = Column(Float, default=0.0)
    notes = Column(String, nullable=True)

class SalesOrderLine(Base):
    __tablename__ = "sales_order_lines"
    id = Column(Integer, primary_key=True, index=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id"))
    item_id = Column(Integer, ForeignKey("inventory_items.id"))
    quantity = Column(Float)
    unit_price = Column(Float)
    total = Column(Float)

class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id"), nullable=True)
    invoice_number = Column(String, unique=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    issue_date = Column(DateTime, default=datetime.utcnow)
    due_date = Column(DateTime, nullable=True)
    total_amount = Column(Float)
    status = Column(String, default="UNPAID")

class PettyCash(Base):
    __tablename__ = "petty_cash"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    amount = Column(Float)
    reason = Column(String)
    requested_by = Column(Integer, ForeignKey("employees.id"))
    status = Column(String, default="PENDING")
    approved_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class LegalMemo(Base):
    __tablename__ = "legal_memos"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    title = Column(String)
    content = Column(String)
    created_by = Column(Integer, ForeignKey("employees.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

class FinancialBond(Base):
    __tablename__ = "financial_bonds"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    bond_type = Column(String)
    amount = Column(Float)
    description = Column(String)
    posted_by = Column(Integer, ForeignKey("employees.id"))
    status = Column(String, default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow)

class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    request_type = Column(String)
    reference_id = Column(String)
    description = Column(String)
    amount = Column(Float, default=0.0)
    status = Column(String, default="PENDING")
    approved_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class TaskResponse(Base):
    __tablename__ = "task_responses"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    employee_id = Column(Integer, ForeignKey("employees.id"))
    status = Column(String)
    comment = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    task = relationship("Task", back_populates="responses")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    title = Column(String)
    description = Column(String, nullable=True)
    assigned_to = Column(Integer, ForeignKey("employees.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("employees.id"))
    status = Column(String, default="TODO")
    priority = Column(String, default="MEDIUM")
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    responses = relationship("TaskResponse", back_populates="task", order_by="TaskResponse.created_at.desc()")
    assigned_employee = relationship("Employee", foreign_keys="[Task.assigned_to]")

class ComplianceItem(Base):
    __tablename__ = "compliance_items"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    name = Column(String) # e.g., "Trade License", "VAT Filing"
    category = Column(String) # Monthly, Annual, Tender-Specific
    expiry_date = Column(DateTime)
    owner_role = Column(String) # HR, Accountant, Finance Manager
    status = Column(String, default="VALID") # VALID, WARNING, CRITICAL, EXPIRED
    alert_30_sent = Column(Boolean, default=False)
    alert_15_sent = Column(Boolean, default=False)
    alert_3_sent = Column(Boolean, default=False)
    last_updated = Column(DateTime, default=datetime.utcnow)

class Workflow(Base):
    __tablename__ = "workflows"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    sop_code = Column(String) # e.g., SOP-001
    sop_name = Column(String)
    reference_id = Column(String, nullable=True) # e.g., Tender ID or License ID
    status = Column(String, default="IN_PROGRESS") # IN_PROGRESS, COMPLETED, BLOCKED
    created_by = Column(Integer, ForeignKey("employees.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

class WorkflowStep(Base):
    __tablename__ = "workflow_steps"
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"))
    step_number = Column(Integer)
    step_name = Column(String)
    assigned_role = Column(String) # e.g., Bid Operator, GM
    status = Column(String, default="PENDING") # PENDING, DONE
    notes = Column(String, nullable=True)
    completed_at = Column(DateTime, nullable=True)

class IncomingDocument(Base):
    __tablename__ = "incoming_documents" # DM-001
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    received_date = Column(DateTime, default=datetime.utcnow)
    sender = Column(String)
    description = Column(String)
    temp_doc_number = Column(String)
    department = Column(String)
    status = Column(String, default="PENDING_REVIEW")

class DocumentMovement(Base):
    __tablename__ = "document_movements" # DM-002
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    doc_reference = Column(String)
    requester = Column(String)
    purpose = Column(String)
    date_out = Column(DateTime, default=datetime.utcnow)
    expected_return = Column(DateTime)
    date_in = Column(DateTime, nullable=True)
    status = Column(String, default="CHECKED_OUT")

class DailyFilingChecklist(Base):
    __tablename__ = "daily_filing_checklists" # DM-006
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    checklist_date = Column(DateTime, default=datetime.utcnow)
    completed_by = Column(Integer, ForeignKey("employees.id"))
    all_logged = Column(Boolean, default=False)
    all_scanned = Column(Boolean, default=False)
    all_filed = Column(Boolean, default=False)
    index_updated = Column(Boolean, default=False)
    cabinets_locked = Column(Boolean, default=False)
    supplies_checked = Column(Boolean, default=False)
    is_signed = Column(Boolean, default=False)
