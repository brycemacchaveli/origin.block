import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import Card from '../../components/Card';
import Button from '../../components/Button';
import { mockLoans, mockComplianceEvents } from '../../services/mockData';
import { LoanStatus, ComplianceEventType } from '../../types';

const DashboardPage: React.FC = () => {
  const { user } = useAuth();

  const activeLoans = mockLoans.filter(l => l.status === LoanStatus.UnderReview).length;
  const complianceAlerts = mockComplianceEvents.filter(e => e.eventType === ComplianceEventType.Alert || e.eventType === ComplianceEventType.Violation).length;

  const tasks = [
    { text: `Review ${activeLoans} pending loan applications`, link: '#/loans' },
    { text: `Address ${complianceAlerts} open compliance alerts`, link: '#/compliance' },
    { text: `Generate Q4 audit report`, link: '#/audit' },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-sans font-bold text-gray-900 leading-tight text-2xl sm:text-3xl">
          Good Morning, {user?.name}
        </h1>
        <p className="mt-1 font-sans text-base text-gray-600">Here's what's happening today.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <h3 className="font-sans font-semibold text-gray-800 text-lg">Active Loan Applications</h3>
          <p className="mt-2 text-4xl font-bold text-brand-primary">{mockLoans.length}</p>
        </Card>
        <Card>
          <h3 className="font-sans font-semibold text-gray-800 text-lg">Pending Review</h3>
          <p className="mt-2 text-4xl font-bold text-brand-primary">{activeLoans}</p>
        </Card>
        <Card>
          <h3 className="font-sans font-semibold text-gray-800 text-lg">Open Compliance Alerts</h3>
          <p className="mt-2 text-4xl font-bold text-brand-error">{complianceAlerts}</p>
        </Card>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <h3 className="font-sans font-semibold text-gray-800 text-lg mb-4">My Tasks</h3>
          <ul className="space-y-3">
            {tasks.map((task, index) => (
              <li key={index} className="p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
                <Link to={task.link} className="font-medium text-gray-800 hover:text-brand-primary">
                  {task.text}
                </Link>
              </li>
            ))}
          </ul>
        </Card>
        
        <Card>
          <h3 className="font-sans font-semibold text-gray-800 text-lg mb-4">Quick Actions</h3>
          <div className="flex flex-col sm:flex-row gap-4">
            <Link to="#/loans/new" className="w-full">
              <Button variant="primary" className="w-full">New Loan Application</Button>
            </Link>
            <Link to="#/customers" className="w-full">
              <Button variant="secondary" className="w-full">View Customers</Button>
            </Link>
          </div>
        </Card>
      </div>

    </div>
  );
};

export default DashboardPage;