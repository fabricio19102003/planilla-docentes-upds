import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import { apiErrorMessage, passwordIssues } from '../src/lib/userCredentials.ts'

const root = resolve(import.meta.dirname, '..')
const usersPage = readFileSync(resolve(root, 'src/pages/UsersPage.tsx'), 'utf8')

test('passwordIssues mirrors the backend password rules', () => {
  assert.deepEqual(passwordIssues('Prueba123'), [])
  assert.deepEqual(passwordIssues('1234'), [
    'Al menos 8 caracteres',
    'Al menos una mayúscula',
    'Al menos una minúscula',
  ])
  assert.deepEqual(passwordIssues('prueba123'), ['Al menos una mayúscula'])
  assert.deepEqual(passwordIssues('PRUEBA123'), ['Al menos una minúscula'])
  assert.deepEqual(passwordIssues('PruebaABC'), ['Al menos un número'])
  assert.deepEqual(passwordIssues('Prueba1'), ['Al menos 8 caracteres'])
})

test('apiErrorMessage returns a string backend detail as is', () => {
  const err = { response: { status: 409, data: { detail: "Ya existe un usuario con CI '123'" } } }
  assert.equal(apiErrorMessage(err, 'fallback'), "Ya existe un usuario con CI '123'")
})

test('apiErrorMessage flattens FastAPI validation errors', () => {
  const err = {
    response: {
      status: 422,
      data: {
        detail: [
          { loc: ['body', 'password'], msg: 'Value error, La contraseña debe incluir al menos una mayúscula' },
        ],
      },
    },
  }
  assert.equal(apiErrorMessage(err, 'fallback'), 'La contraseña debe incluir al menos una mayúscula')
})

test('apiErrorMessage falls back when there is no usable detail', () => {
  assert.equal(apiErrorMessage(new Error('Network Error'), 'No se pudo crear el usuario.'), 'No se pudo crear el usuario.')
  assert.equal(apiErrorMessage({ response: { data: { detail: [] } } }, 'fb'), 'fb')
})

test('UsersPage no longer blames a duplicated CI for every failure', () => {
  assert.doesNotMatch(usersPage, /Verificá que el CI no esté duplicado/)
  assert.doesNotMatch(usersPage, /al menos 4 caracteres/)
  assert.match(usersPage, /apiErrorMessage\(/)
  assert.match(usersPage, /passwordIssues\(/)
})
