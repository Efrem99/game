"""
ShopManager — Bridge between DialogCinematicManager and ShopUI.

Created lazily upon first use. Called by dialog actions when user
picks "Show me your wares" in merchant dialogue.
"""

from utils.logger import logger
from managers.runtime_data_access import load_data_recursive


class ShopManager:
    """Manages shop state and merchant inventories."""

    def __init__(self, app):
        self.app = app
        self._ui = None  # Lazy import to avoid circular deps
        self._merchant_inventories = {}
        self._load_merchant_inventories()

    def _ensure_ui(self):
        if self._ui is None:
            from ui.shop_ui import ShopUI
            self._ui = ShopUI(self.app)
        return self._ui

    def _load_merchant_inventories(self):
        """Load per-merchant item lists from data backend / data/shops."""
        self._merchant_inventories = {}
        payload = load_data_recursive(self.app, "shops", default={})
        if not isinstance(payload, dict):
            return
        for key, data in payload.items():
            if not isinstance(data, dict):
                continue
            merchant_id = str(data.get("merchant_id", key) or key).strip()
            items = data.get("items", [])
            if isinstance(items, list) and merchant_id:
                self._merchant_inventories[merchant_id] = {
                    "name": data.get("merchant_name", "Merchant"),
                    "items": items,
                }

    def open(self, npc_id="merchant"):
        """Open the shop UI for a given NPC/merchant."""
        ui = self._ensure_ui()

        # Try to find merchant-specific inventory
        inv_data = self._merchant_inventories.get(npc_id)
        if inv_data:
            name = inv_data.get("name", "Merchant")
            items = inv_data.get("items", None)
        else:
            # Fallback: use NPC display name + default items
            name = self._get_npc_display_name(npc_id)
            items = None  # Will load default from data/items/

        ui.show(npc_id, merchant_name=name, items=items)
        logger.info(f"[ShopManager] Opened shop for '{npc_id}' as '{name}'")

    def close(self):
        if self._ui:
            self._ui.hide()

    def is_open(self):
        return bool(self._ui and self._ui.is_visible())

    def _get_npc_display_name(self, npc_id):
        """Try to pull NPC display name from data manager."""
        dm = getattr(self.app, "data_manager", None) or getattr(self.app, "data_mgr", None)
        if dm and hasattr(dm, "npcs"):
            npc_data = dm.npcs.get(npc_id, {})
            if isinstance(npc_data, dict):
                return npc_data.get("display_name", npc_data.get("name", "Merchant"))
        return npc_id.replace("_", " ").title()
