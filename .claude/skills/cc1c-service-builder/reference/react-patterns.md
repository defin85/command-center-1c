# React Component Patterns

## Form Component Pattern

```typescript
// YourForm.tsx
import React from 'react';
import { Form, Input, Button, message } from 'antd';

interface YourFormProps {
  onSubmit: (values: any) => Promise<void>;
}

const YourForm: React.FC<YourFormProps> = ({ onSubmit }) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = React.useState(false);

  const handleSubmit = async (values: any) => {
    try {
      setLoading(true);
      await onSubmit(values);
      message.success('Успешно сохранено');
      form.resetFields();
    } catch (error) {
      message.error('Ошибка при сохранении');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Form form={form} onFinish={handleSubmit} layout="vertical">
      <Form.Item name="name" label="Название" rules={[{ required: true }]}>
        <Input />
      </Form.Item>

      <Form.Item>
        <Button type="primary" htmlType="submit" loading={loading}>
          Сохранить
        </Button>
      </Form.Item>
    </Form>
  );
};

export default YourForm;
```

## Store Pattern (Zustand)

```typescript
// stores/useYourStore.ts
import create from 'zustand';
import { yourApi } from '../api/endpoints/your';

interface YourStore {
  items: any[];
  loading: boolean;
  fetchItems: () => Promise<void>;
  createItem: (data: any) => Promise<void>;
}

export const useYourStore = create<YourStore>((set) => ({
  items: [],
  loading: false,

  fetchItems: async () => {
    set({ loading: true });
    try {
      const items = await yourApi.getAll();
      set({ items, loading: false });
    } catch (error) {
      set({ loading: false });
    }
  },

  createItem: async (data: any) => {
    await yourApi.create(data);
    // Refresh list
    const items = await yourApi.getAll();
    set({ items });
  },
}));
```
