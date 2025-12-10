# DynamicForm Test Suite

Comprehensive test coverage for the DynamicForm component and its dependencies.

## Test Structure

```
__tests__/
├── hooks.test.ts          # Tests for custom hooks
├── renderers.test.tsx     # Tests for field renderers
├── utils.test.ts          # Tests for utility functions
└── DynamicForm.test.tsx   # Integration tests
```

## Coverage

### Hooks (31 tests)

**useSchemaValidation**
- ✓ Validates required fields
- ✓ Validates string minLength
- ✓ Validates number minimum and maximum
- ✓ Validates email format
- ✓ Returns empty errors for valid data
- ✓ Provides getFieldError helper
- ✓ Clears errors when clearErrors is called

**useConditionalFields**
- ✓ Shows field when condition is met with eq operator
- ✓ Hides field when condition is not met
- ✓ Shows field with neq operator when values differ
- ✓ Shows field with in operator when value is in array
- ✓ Hides field with in operator when value is not in array
- ✓ Shows field without conditional always
- ✓ Filters visible fields correctly

**useFieldOrder**
- ✓ Sorts fields by x-order
- ✓ Places fields without order at the end
- ✓ Returns field count
- ✓ Provides getField helper
- ✓ Skips readOnly fields

### Renderers (25 tests)

**TextFieldRenderer**
- ✓ Renders text input
- ✓ Renders textarea for textarea type
- ✓ Renders password input for password type
- ✓ Shows placeholder
- ✓ Calls onChange when value changes
- ✓ Respects disabled state
- ✓ Respects maxLength

**NumberFieldRenderer**
- ✓ Renders input number
- ✓ Respects min and max values
- ✓ Calls onChange with number value
- ✓ Uses step 1 for integer type
- ✓ Respects disabled state

**BooleanFieldRenderer**
- ✓ Renders switch
- ✓ Shows checked state
- ✓ Calls onChange with boolean value
- ✓ Respects disabled state

**SelectFieldRenderer**
- ✓ Renders select with options
- ✓ Renders multi-select mode
- ✓ Calls onChange with selected value
- ✓ Respects disabled state

**DateFieldRenderer**
- ✓ Renders date picker
- ✓ Renders datetime picker with showTime
- ✓ Calls onChange with dayjs formatted value
- ✓ Respects disabled state
- ✓ Formats datetime with ISO string

### Utils (30 tests)

**schemaParser**
- ✓ Infers text type from string
- ✓ Infers textarea from string with long maxLength
- ✓ Infers number type from integer
- ✓ Infers select type from enum
- ✓ Infers boolean type
- ✓ Infers date type from format
- ✓ Uses explicit x-field-type
- ✓ Parses schema properties into field configs
- ✓ Skips readOnly fields
- ✓ Extracts conditional config
- ✓ Formats field names (snake_case and camelCase)
- ✓ Extracts select options from enum
- ✓ Sorts fields by order

**defaults**
- ✓ Extracts default values from schema
- ✓ Returns empty object for schema without defaults
- ✓ Handles nested object defaults
- ✓ Returns explicit default value
- ✓ Merges values with defaults
- ✓ Detects empty values (null, undefined, empty string, empty array)
- ✓ Cleans values by removing empty entries
- ✓ Coerces values to appropriate types

### Integration (18 tests)

**DynamicForm**
- ✓ Renders all fields from schema
- ✓ Shows required indicator for required fields
- ✓ Shows field description as help text
- ✓ Calls onChange when field value changes
- ✓ Hides conditional fields when condition not met
- ✓ Shows conditional field when condition is met
- ✓ Shows validation errors
- ✓ Respects disabled prop
- ✓ Sorts fields by x-order
- ✓ Uses horizontal layout when specified
- ✓ Shows "No fields to display" when no fields exist
- ✓ Handles multiple field types in one form
- ✓ Handles complex conditional logic with multiple conditions
- ✓ Clears validation errors when field value changes

## Running Tests

```bash
# Run all tests
npm test

# Run tests in watch mode
npm test

# Run tests once
npm run test:run

# Run tests with UI
npm run test:ui

# Run tests with coverage
npm run test:coverage
```

## Test Technologies

- **Vitest**: Fast unit test framework
- **@testing-library/react**: React component testing utilities
- **@testing-library/user-event**: User interaction simulation
- **jsdom**: Browser environment simulation

## Best Practices

1. **Use descriptive test names**: Each test clearly describes what it tests
2. **Follow AAA pattern**: Arrange, Act, Assert
3. **Avoid testing implementation details**: Focus on user-facing behavior
4. **Use semantic queries**: Prefer `getByRole`, `getByLabelText` over `getByTestId`
5. **Wait for async updates**: Use `waitFor` for React state updates
6. **Mock external dependencies**: Don't rely on real API calls or file system

## Coverage Goals

- **Lines**: > 90%
- **Functions**: > 90%
- **Branches**: > 80%
- **Statements**: > 90%

## Notes

- Tests use Ant Design components, which may have internal implementation details
- Some tests verify component behavior rather than exact DOM structure
- Password inputs and select components require special handling due to Ant Design's implementation
- Validation tests use `waitFor` to handle React state updates asynchronously
