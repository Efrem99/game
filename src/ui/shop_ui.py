"""
ShopUI — RPG buy/sell merchant interface for King Wizard.

Displays merchant's inventory in a parchment-themed panel.
Player can browse items, see stats/prices, buy, and sell from inventory.
"""

import json
import os
import math
from direct.gui.DirectGui import (
    DirectFrame, DirectButton, DirectScrolledFrame, OnscreenText, DGG
)
from panda3d.core import TextNode, TransparencyAttrib, LColor
from direct.showbase.ShowBaseGlobal import globalClock
from managers.runtime_data_access import load_data_recursive
from ui.design_system import THEME, title_font, body_font, ParchmentPanel, place_ui_on_top
from utils.logger import logger


class ShopUI:
    """Full-featured merchant shop UI with buy/sell tabs."""

    def __init__(self, app):
        self.app = app
        self._visible = False
        self._merchant_id = ""
        self._merchant_name = ""
        self._merchant_items = []  # [{id, name, price, type, description, ...}]
        self._selected_idx = -1
        self._mode = "buy"  # "buy" or "sell"

        # ── Root frame ──
        self.root = DirectFrame(
            frameColor=(0, 0, 0, 0.6),
            frameSize=(-2, 2, -1, 1),
            parent=app.aspect2d,
        )
        place_ui_on_top(self.root, 96)

        # ── Panel ──
        self.panel = ParchmentPanel(
            app,
            parent=self.root,
            frameSize=(-0.95, 0.95, -0.75, 0.75),
            pos=(0, 0, 0),
        )

        # ── Title ──
        self.title_text = OnscreenText(
            text="Merchant",
            pos=(0, 0.62),
            scale=0.06,
            fg=THEME["gold_primary"],
            shadow=(0, 0, 0, 0.8),
            font=title_font(app),
            align=TextNode.ACenter,
            parent=self.panel,
            mayChange=True,
        )

        # ── Gold display ──
        self.gold_text = OnscreenText(
            text="Gold: 0",
            pos=(0.85, 0.62),
            scale=0.04,
            fg=THEME.get("gold_soft", (1, 0.85, 0.3, 1)),
            shadow=(0, 0, 0, 0.7),
            font=body_font(app),
            align=TextNode.ARight,
            parent=self.panel,
            mayChange=True,
        )

        # ── Tab buttons (Buy / Sell) ──
        btn_style = {
            "frameColor": (0.35, 0.25, 0.15, 0.9),
            "text_fg": THEME["text_main"],
            "text_shadow": (0, 0, 0, 0.6),
            "text_font": body_font(app),
            "relief": DGG.FLAT,
        }
        self.buy_btn = DirectButton(
            text="Buy",
            pos=(-0.45, 0, 0.50),
            scale=0.045,
            command=self._switch_to_buy,
            parent=self.panel,
            **btn_style,
        )
        self.sell_btn = DirectButton(
            text="Sell",
            pos=(-0.20, 0, 0.50),
            scale=0.045,
            command=self._switch_to_sell,
            parent=self.panel,
            **btn_style,
        )

        # ── Scrollable item list ──
        self.scroll_frame = DirectScrolledFrame(
            frameColor=(0.20, 0.16, 0.10, 0.5),
            frameSize=(-0.88, 0.30, -0.65, 0.44),
            canvasSize=(-0.86, 0.28, -2.0, 0.0),
            scrollBarWidth=0.03,
            verticalScroll_relief=DGG.FLAT,
            verticalScroll_frameColor=(0.4, 0.3, 0.2, 0.6),
            verticalScroll_thumb_frameColor=(0.6, 0.5, 0.35, 0.9),
            parent=self.panel,
            autoHideScrollBars=True,
        )
        self._item_buttons = []

        # ── Detail panel (right side) ──
        self.detail_frame = DirectFrame(
            frameColor=(0.22, 0.18, 0.12, 0.5),
            frameSize=(0.35, 0.88, -0.65, 0.44),
            parent=self.panel,
        )
        self.detail_name = OnscreenText(
            text="",
            pos=(0.61, 0.36),
            scale=0.045,
            fg=THEME["gold_primary"],
            shadow=(0, 0, 0, 0.7),
            font=title_font(app),
            align=TextNode.ACenter,
            parent=self.panel,
            mayChange=True,
            wordwrap=12,
        )
        self.detail_type = OnscreenText(
            text="",
            pos=(0.61, 0.28),
            scale=0.032,
            fg=THEME["text_muted"],
            font=body_font(app),
            align=TextNode.ACenter,
            parent=self.panel,
            mayChange=True,
        )
        self.detail_desc = OnscreenText(
            text="",
            pos=(0.41, 0.20),
            scale=0.030,
            fg=THEME["text_main"],
            font=body_font(app),
            align=TextNode.ALeft,
            parent=self.panel,
            mayChange=True,
            wordwrap=16,
        )
        self.detail_stats = OnscreenText(
            text="",
            pos=(0.41, 0.02),
            scale=0.032,
            fg=(0.7, 0.9, 0.7, 1),
            font=body_font(app),
            align=TextNode.ALeft,
            parent=self.panel,
            mayChange=True,
            wordwrap=16,
        )
        self.detail_price = OnscreenText(
            text="",
            pos=(0.61, -0.12),
            scale=0.045,
            fg=THEME.get("gold_soft", (1, 0.85, 0.3, 1)),
            shadow=(0, 0, 0, 0.6),
            font=title_font(app),
            align=TextNode.ACenter,
            parent=self.panel,
            mayChange=True,
        )

        # ── Action button (Buy / Sell) ──
        self.action_btn = DirectButton(
            text="Buy",
            pos=(0.61, 0, -0.25),
            scale=0.05,
            command=self._do_action,
            parent=self.panel,
            frameColor=(0.25, 0.55, 0.20, 0.9),
            text_fg=(1, 1, 1, 1),
            text_shadow=(0, 0, 0, 0.8),
            text_font=title_font(app),
            relief=DGG.FLAT,
            frameSize=(-3.5, 3.5, -0.8, 1.1),
        )
        self.action_btn.hide()

        # ── Close button ──
        self.close_btn = DirectButton(
            text="Close [Esc]",
            pos=(0.61, 0, -0.55),
            scale=0.04,
            command=self.hide,
            parent=self.panel,
            frameColor=(0.45, 0.18, 0.15, 0.8),
            text_fg=(1, 0.9, 0.8, 1),
            text_font=body_font(app),
            relief=DGG.FLAT,
        )

        self.root.hide()

    # ── Public API ──

    def show(self, merchant_id, merchant_name="Merchant", items=None):
        """Open the shop UI with the given merchant's inventory."""
        self._merchant_id = merchant_id
        self._merchant_name = merchant_name
        self._merchant_items = list(items) if items else self._load_default_shop()
        self._mode = "buy"
        self._selected_idx = -1
        self._visible = True

        self.title_text.setText(merchant_name)
        self._update_gold_display()
        self._populate_items()
        self._clear_detail()

        self.root.show()

        # Register ESC key
        self.app.accept("escape", self.hide)

        # Set state to menu
        if hasattr(self.app, "state_mgr"):
            self.app.state_mgr.set_state(self.app.GameState.MENU)

        logger.info(f"[ShopUI] Opened shop: {merchant_name} ({len(self._merchant_items)} items)")

    def hide(self):
        """Close the shop UI."""
        self._visible = False
        self.root.hide()
        self.app.ignore("escape")

        if hasattr(self.app, "state_mgr"):
            try:
                self.app.state_mgr.set_state(self.app.GameState.PLAYING)
            except Exception:
                pass

        logger.info("[ShopUI] Shop closed.")

    def is_visible(self):
        return self._visible

    # ── Data ──

    def _load_default_shop(self):
        """Load default merchant items from the active runtime data backend."""
        default_prices = {
            "weapon": 50, "armor": 75, "consumable": 15,
            "offhand": 40, "artifact": 120,
        }
        category_order = {
            "weapon": 0,
            "armor": 1,
            "consumable": 2,
            "offhand": 3,
            "artifact": 4,
        }
        data_mgr = getattr(self.app, "data_mgr", None)
        raw_items = getattr(data_mgr, "items", None) if data_mgr is not None else None
        if not isinstance(raw_items, dict) or not raw_items:
            raw_items = load_data_recursive(self.app, "items", default={})
        if not isinstance(raw_items, dict):
            return []

        sortable_rows = []
        for item_id, payload in raw_items.items():
            if not isinstance(payload, dict):
                continue
            item_type = str(payload.get("type", "")).strip().lower()
            item_name = str(payload.get("name", item_id)).strip().lower()
            sortable_rows.append(
                (
                    category_order.get(item_type, 99),
                    item_name,
                    str(item_id).strip().lower(),
                    item_id,
                    payload,
                )
            )

        items = []
        for _order, _name, _item_id_key, item_id, payload in sorted(sortable_rows):
            item = dict(payload)
            item.setdefault("id", str(item_id))
            if "price" not in item:
                item_type = str(item.get("type", "")).strip().lower()
                item["price"] = default_prices.get(item_type, 25)
            items.append(item)
        return items

    def _get_player_gold(self):
        if hasattr(self.app, "player") and self.app.player:
            return int(getattr(self.app.player, "gold", 100))
        return 100

    def _set_player_gold(self, amount):
        if hasattr(self.app, "player") and self.app.player:
            self.app.player.gold = max(0, int(amount))

    def _get_player_inventory(self):
        if hasattr(self.app, "player") and self.app.player:
            inv = getattr(self.app.player, "inventory", None)
            if isinstance(inv, list):
                return inv
        return []

    # ── UI Updates ──

    def _update_gold_display(self):
        gold = self._get_player_gold()
        self.gold_text.setText(f"Gold: {gold}")

    def _switch_to_buy(self):
        self._mode = "buy"
        self._selected_idx = -1
        self._populate_items()
        self._clear_detail()

    def _switch_to_sell(self):
        self._mode = "sell"
        self._selected_idx = -1
        self._populate_items()
        self._clear_detail()

    def _populate_items(self):
        """Build the item list buttons."""
        # Clear old buttons
        for btn in self._item_buttons:
            btn.destroy()
        self._item_buttons = []

        if self._mode == "buy":
            items = self._merchant_items
            # Highlight buy tab
            self.buy_btn["frameColor"] = (0.5, 0.38, 0.22, 1.0)
            self.sell_btn["frameColor"] = (0.35, 0.25, 0.15, 0.9)
        else:
            items = self._get_player_inventory()
            self.sell_btn["frameColor"] = (0.5, 0.38, 0.22, 1.0)
            self.buy_btn["frameColor"] = (0.35, 0.25, 0.15, 0.9)

        canvas = self.scroll_frame.getCanvas()
        y = -0.02
        row_h = 0.08

        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue

            name = str(item.get("name", item.get("id", "???")))
            price = int(item.get("price", 0))
            item_type = str(item.get("type", "")).capitalize()

            if self._mode == "sell":
                price = max(1, price // 2)  # Sell at half price

            label = f"{name}  ({price}g)"

            btn = DirectButton(
                text=label,
                text_scale=0.6,
                text_align=TextNode.ALeft,
                text_fg=THEME["text_main"],
                text_font=body_font(self.app),
                frameColor=(0.28, 0.22, 0.14, 0.6),
                frameSize=(-0.2, 16.0, -0.45, 0.75),
                relief=DGG.FLAT,
                pos=(-0.82, 0, y),
                scale=0.055,
                parent=canvas,
                command=self._select_item,
                extraArgs=[idx],
            )
            self._item_buttons.append(btn)
            y -= row_h

        # Update canvas size
        total_h = max(2.0, len(items) * row_h + 0.1)
        self.scroll_frame["canvasSize"] = (-0.86, 0.28, -total_h, 0.0)

    def _select_item(self, idx):
        """Select an item and show its details."""
        self._selected_idx = idx

        if self._mode == "buy":
            items = self._merchant_items
        else:
            items = self._get_player_inventory()

        if idx < 0 or idx >= len(items):
            self._clear_detail()
            return

        item = items[idx]
        name = str(item.get("name", "???"))
        item_type = str(item.get("type", "item")).capitalize()
        desc = str(item.get("description", "No description."))
        price = int(item.get("price", 0))

        # Build stats string
        stats_parts = []
        if "power" in item:
            stats_parts.append(f"Power: {item['power']}")
        if "armor" in item:
            stats_parts.append(f"Armor: {item['armor']}")
        if "heal_value" in item or item.get("effect") == "heal":
            val = item.get("heal_value", item.get("value", 0))
            stats_parts.append(f"Heals: {val} HP")
        if item.get("effect") == "restore_mana":
            stats_parts.append(f"Restores: {item.get('value', 0)} MP")
        stats_str = "\n".join(stats_parts) if stats_parts else ""

        if self._mode == "sell":
            price = max(1, price // 2)

        self.detail_name.setText(name)
        self.detail_type.setText(f"[{item_type}]")
        self.detail_desc.setText(desc)
        self.detail_stats.setText(stats_str)
        self.detail_price.setText(f"{price} Gold")

        # Action button
        if self._mode == "buy":
            can_afford = self._get_player_gold() >= price
            self.action_btn["text"] = "Buy"
            self.action_btn["frameColor"] = (0.25, 0.55, 0.20, 0.9) if can_afford else (0.4, 0.4, 0.4, 0.5)
        else:
            self.action_btn["text"] = "Sell"
            self.action_btn["frameColor"] = (0.55, 0.40, 0.15, 0.9)
        self.action_btn.show()

        # Highlight selected button
        for i, btn in enumerate(self._item_buttons):
            if i == idx:
                btn["frameColor"] = (0.45, 0.35, 0.18, 0.9)
            else:
                btn["frameColor"] = (0.28, 0.22, 0.14, 0.6)

    def _clear_detail(self):
        self.detail_name.setText("")
        self.detail_type.setText("")
        self.detail_desc.setText("")
        self.detail_stats.setText("")
        self.detail_price.setText("")
        self.action_btn.hide()

    def _do_action(self):
        """Execute buy or sell."""
        if self._mode == "buy":
            self._do_buy()
        else:
            self._do_sell()

    def _do_buy(self):
        if self._selected_idx < 0 or self._selected_idx >= len(self._merchant_items):
            return
        item = self._merchant_items[self._selected_idx]
        price = int(item.get("price", 0))
        gold = self._get_player_gold()

        if gold < price:
            logger.info("[ShopUI] Not enough gold!")
            return

        self._set_player_gold(gold - price)
        # Add to player inventory
        inv = self._get_player_inventory()
        inv.append(dict(item))

        self._update_gold_display()
        self._select_item(self._selected_idx)  # Refresh affordability
        logger.info(f"[ShopUI] Bought: {item.get('name')} for {price}g")

    def _do_sell(self):
        inv = self._get_player_inventory()
        if self._selected_idx < 0 or self._selected_idx >= len(inv):
            return
        item = inv[self._selected_idx]
        sell_price = max(1, int(item.get("price", 0)) // 2)

        gold = self._get_player_gold()
        self._set_player_gold(gold + sell_price)
        inv.pop(self._selected_idx)

        self._update_gold_display()
        self._selected_idx = -1
        self._populate_items()
        self._clear_detail()
        logger.info(f"[ShopUI] Sold: {item.get('name')} for {sell_price}g")

    def destroy(self):
        self.root.destroy()
