# docente-profile-management Specification

## Purpose

Define required behavior for docente profile data and profile photo management, including admin actions, docente self-service toggles, backend authorization, and safe image validation.

## Requirements

### Requirement: Admin manages docente profile photo lifecycle

The system MUST allow admins to upload, replace, and remove a docente profile photo for any docente record.

#### Scenario: Admin uploads or replaces photo

- GIVEN an authenticated admin and an existing docente
- WHEN the admin submits a valid image file for that docente
- THEN the system stores the new photo and associates it with that docente
- AND any previously associated photo is no longer the active profile photo

#### Scenario: Admin removes photo

- GIVEN an authenticated admin and a docente with an existing photo
- WHEN the admin requests photo removal
- THEN the system removes the active photo association from the docente

### Requirement: Avatar display uses photo with initials fallback

The system MUST expose docente avatar/profile photo data so UI clients can render the uploaded photo, and MUST support initials fallback when no active photo is available.

#### Scenario: Photo exists

- GIVEN a docente with an active profile photo
- WHEN profile or header data is requested
- THEN the response includes a resolvable avatar/photo reference for that docente

#### Scenario: No photo exists

- GIVEN a docente without an active profile photo
- WHEN profile or header data is requested
- THEN the response indicates no photo reference
- AND clients can render initials fallback without error

### Requirement: Admin controls docente self-edit permissions

The system MUST provide admin-configurable settings for docente self-edit permissions:
- `DOCENTE_CAN_EDIT_PROFILE`
- `DOCENTE_CAN_EDIT_PHOTO`

#### Scenario: Admin updates settings

- GIVEN an authenticated admin
- WHEN the admin enables or disables either setting
- THEN the system persists the updated setting values for subsequent permission checks

### Requirement: Backend enforces docente edit authorization

The backend MUST enforce permission checks for docente self-service profile-data mutations and MUST NOT rely only on frontend visibility controls.

#### Scenario: Profile edit blocked by setting

- GIVEN an authenticated docente and `DOCENTE_CAN_EDIT_PROFILE=false`
- WHEN the docente submits a profile data update
- THEN the backend rejects the request as unauthorized

#### Scenario: Profile edit allowed by setting

- GIVEN an authenticated docente and `DOCENTE_CAN_EDIT_PROFILE=true`
- WHEN the docente submits a valid profile data update
- THEN the backend accepts and persists the update

### Requirement: Backend enforces docente photo authorization

The backend MUST enforce permission checks for docente self-service photo upload, replace, and removal operations.

#### Scenario: Photo mutation blocked by setting

- GIVEN an authenticated docente and `DOCENTE_CAN_EDIT_PHOTO=false`
- WHEN the docente attempts to upload, replace, or remove a photo
- THEN the backend rejects the request as unauthorized

#### Scenario: Photo mutation allowed by setting

- GIVEN an authenticated docente and `DOCENTE_CAN_EDIT_PHOTO=true`
- WHEN the docente submits a valid photo mutation request
- THEN the backend applies the requested change

### Requirement: Image upload validation is safe and strict

The system MUST validate uploaded image files for allowed content type and maximum file size, and MUST reject invalid uploads safely without mutating docente photo state.

#### Scenario: Invalid file type

- GIVEN an upload request with a non-image or disallowed image type
- WHEN validation runs
- THEN the system rejects the upload with a validation error
- AND no photo data is created or modified

#### Scenario: Oversized file

- GIVEN an upload request with a file exceeding configured maximum size
- WHEN validation runs
- THEN the system rejects the upload with a validation error
- AND no photo data is created or modified
