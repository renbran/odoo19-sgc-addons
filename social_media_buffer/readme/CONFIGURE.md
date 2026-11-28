In Buffer, open **Settings > API** and create an API key. Do not put the key in
source code, configuration files under version control, or client-side assets.

In Odoo, a system administrator opens **Social Media > Configuration > Buffer
Connections** and creates a connection:

- enter a recognizable name and the Buffer API key;
- optionally enter a Buffer organization ID to import only that organization;
- leave the organization ID empty to import every organization available to the
  key.

Save the connection and press **Import Channels**. The operation can be repeated
safely: existing channels are updated by their Buffer channel ID rather than
duplicated. Social media administrators can run the import with a key already
stored by a system administrator, but cannot read the protected key field.

The key is stored in Odoo with access restricted to the System group. API calls
are made only by the Odoo server.
