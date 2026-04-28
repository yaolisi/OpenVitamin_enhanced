import { describe, expect, it, vi } from 'vitest'

import {
  PERILLA_SYSTEM_CONFIG_CHANGED,
  SYSTEM_CONFIG_CHANGE_DEBOUNCE_MS,
  notifySystemConfigChanged,
} from '@/constants/platformEvents'

describe('platformEvents', () => {
  it('uses stable custom event name for system config refresh', () => {
    expect(PERILLA_SYSTEM_CONFIG_CHANGED).toBe('perilla:system-config-changed')
  })

  it('debounce default matches composables contract', () => {
    expect(SYSTEM_CONFIG_CHANGE_DEBOUNCE_MS).toBe(400)
  })

  it('notifySystemConfigChanged dispatches on window', () => {
    const spy = vi.fn()
    window.addEventListener(PERILLA_SYSTEM_CONFIG_CHANGED, spy)
    notifySystemConfigChanged()
    expect(spy).toHaveBeenCalledTimes(1)
    window.removeEventListener(PERILLA_SYSTEM_CONFIG_CHANGED, spy)
  })
})
