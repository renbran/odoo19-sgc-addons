# -*- coding: utf-8 -*-
from . import risk_override_wizard
from . import goaml_filing_wizard
# edd_wizard defines aml.edd.wizard and aml.edd.response. It was not
# imported here, so the models never reached the registry and
# views/edd_wizard_views.xml (which IS in the manifest) failed with
# "Model not found: aml.edd.wizard" - breaking every fresh install.
from . import edd_wizard
