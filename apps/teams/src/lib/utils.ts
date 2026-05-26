import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Normaliza un número de teléfono español a formato +34XXXXXXXXX para usar con tel: URI.
 */
export function normalizePhoneEs(raw: string | null | undefined): string | null {
  if (!raw) return null
  const cleaned = raw.replace(/[\s\-()]/g, '')
  if (!cleaned) return null
  if (cleaned.startsWith('+')) return cleaned
  if (cleaned.startsWith('00')) return '+' + cleaned.slice(2)
  // móviles ES empiezan por 6/7, fijos por 8/9
  if (/^[6789]\d{8}$/.test(cleaned)) return '+34' + cleaned
  return cleaned.length >= 9 ? '+' + cleaned : null
}
