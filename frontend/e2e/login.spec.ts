import { expect, test } from '@playwright/test'

import { mockInvalidCredentials } from './support/api'

test('supports keyboard login, password visibility, and invalid credentials feedback', async ({ page }) => {
  await mockInvalidCredentials(page)
  await page.goto('/login')

  const ciInput = page.getByRole('textbox', { name: 'Cédula de Identidad' })
  const passwordInput = page.getByLabel('Contraseña', { exact: true })
  const passwordToggle = page.getByRole('button', { name: 'Mostrar contraseña' })
  const submitButton = page.getByRole('button', { name: 'Ingresar al Sistema' })

  await expect(ciInput).toBeVisible()
  await expect(passwordInput).toHaveAttribute('type', 'password')
  await ciInput.focus()
  await ciInput.fill('12345678')
  await page.keyboard.press('Tab')
  await expect(passwordInput).toBeFocused()
  await passwordInput.fill('wrong-password')
  await page.keyboard.press('Tab')
  await expect(passwordToggle).toBeFocused()
  await page.keyboard.press('Space')
  await expect(passwordInput).toHaveAttribute('type', 'text')
  await expect(page.getByRole('button', { name: 'Ocultar contraseña' })).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(submitButton).toBeFocused()

  const loginRequest = page.waitForRequest(
    (request) => request.method() === 'POST' && new URL(request.url()).pathname === '/api/auth/login',
  )
  await page.keyboard.press('Enter')

  expect((await loginRequest).postDataJSON()).toEqual({ ci: '12345678', password: 'wrong-password' })
  await expect(page.getByRole('alert')).toHaveText('CI o contraseña incorrectos.')
})
