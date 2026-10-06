# Missing Foundation Models - Lightweight Architecture

## 1. Document Management System (DMS)

### `construction.document.folder`
* `name`: Folder Name
* `parent_id`: Parent Folder
* `project_id`: Linked Project
* `folder_type`: (Static/Virtual)
* `sequence`: Sort Order

### `construction.document`
* `name`: Document Title
* `number`: Document Number (PROJECT-CAT-YEAR-SEQ)
* `category`: (Contract, Drawing, BOQ, VO, RFI, Submittal, NCR, etc.)
* `project_id`: Linked Project
* `folder_id`: Folder Reference
* `current_revision_id`: Link to `construction.document.revision`
* `status`: (Draft, Issued, Reviewed, Approved, Closed)
* `issue_date`: Date
* `transmittal_id`: Link to `construction.transmittal`

### `construction.document.revision`
* `document_id`: Parent Document
* `revision_no`: (0, A, B, C, etc.)
* `revision_date`: Date
* `status`: (IFR, IFA, IFC, AS-BUILT)
* `attachment_id`: Odoo `ir.attachment` link
* `prepared_by`: User
* `checked_by`: User
* `approved_by`: User

---

## 2. Site Management

### `construction.site.diary`
* `project_id`: Project
* `date`: Diary Date
* `weather`: (Sunny, Rain, High Wind, etc.)
* `temperature`: Float
* `labor_summary_ids`: One2many `construction.site.diary.labor`
* `equipment_summary_ids`: One2many `construction.site.diary.equipment`
* `activity_ids`: One2many `construction.site.diary.activity`
* `material_ids`: One2many `construction.site.diary.material`
* `issue_ids`: One2many `construction.site.diary.issue`
* `photo_ids`: One2many `ir.attachment` (Photographic Report source)

### `construction.site.diary.activity`
* `diary_id`: Parent
* `description`: Text
* `progress_percent`: Float
* `wbs_id`: WBS Phase

---

## 3. Resource & HSE Tracking

### `construction.equipment`
* `name`: Equipment Name
* `code`: Equipment Code
* `category`: (Heavy, Light, Tool)
* `status`: (Operational, Maintenance, Breakdown)

### `construction.equipment.log`
* `equipment_id`: Equipment
* `project_id`: Project
* `date`: Date
* `hours_utilized`: Float
* `fuel_consumed`: Float

### `construction.labor.attendance`
* `project_id`: Project
* `date`: Date
* `employee_id`: Worker
* `hours`: Float
* `overtime`: Float
* `trade`: Selection (Civil, MEP, etc.)

### `construction.hse.incident`
* `project_id`: Project
* `date`: Date/Time
* `incident_type`: (Near Miss, Injury, Violation, ToolBox Talk)
* `description`: Text
* `severity`: (Low, Medium, High, Critical)
* `status`: (Open, Under Investigation, Closed)

---

## 4. Transmittals

### `construction.transmittal`
* `number`: TRN Number (PROJECT-TRN-YEAR-SEQ)
* `project_id`: Project
* `recipient_id`: Partner
* `subject`: Subject
* `issue_date`: Date
* `state`: (Draft, Issued, Received, Acknowledged)
* `document_ids`: Many2many `construction.document`
