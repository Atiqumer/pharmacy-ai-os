export const INVENTORY_CHANGED_EVENT = 'rxos:inventory-changed';

export function notifyInventoryChanged() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(INVENTORY_CHANGED_EVENT));
  }
}
