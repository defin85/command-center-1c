import { Card, Row, Col, Statistic } from 'antd';
import { ThunderboltOutlined, DatabaseOutlined, CheckCircleOutlined } from '@ant-design/icons';

export const Dashboard = () => {
  return (
    <div>
      <h1>Dashboard</h1>
      <Row gutter={16}>
        <Col span={8}>
          <Card>
            <Statistic
              title="Total Operations"
              value={0}
              prefix={<ThunderboltOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="Active Databases"
              value={0}
              prefix={<DatabaseOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="Success Rate"
              value={0}
              suffix="%"
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};
