module = env["ir.module.module"].search([("name", "=", "sgc_construction_management")])
print(f"Module: {module.name if module else 'NOT FOUND'}, State: {module.state if module else 'N/A'}")

if module:
    data_count = env["ir.model.data"].search_count([("module", "=", "sgc_construction_management")])
    print(f"Total data records: {data_count}")
    
    # Count demo records by model
    demo_models = ["res.partner", "project.project", "project.task", "construction.project", 
                   "construction.boq", "construction.wbs", "construction.work.order",
                   "construction.material.requisition", "construction.subcontract",
                   "construction.hse.incident", "construction.quality.check",
                   "construction.expense", "construction.transmittal", "construction.document",
                   "construction.equipment", "construction.labor.attendance", "construction.site.diary"]
    
    for model_name in demo_models:
        try:
            model = env[model_name]
            count = model.search_count([("create_uid", "!=", False)])
            # Also count records linked to demo data
            demo_ids = env["ir.model.data"].search([
                ("module", "=", "sgc_construction_management"),
                ("model", "=", model_name)
            ])
            print(f"  {model_name}: {len(demo_ids)} demo records")
        except KeyError:
            pass
        except Exception as e:
            print(f"  {model_name}: ERROR {e}")
