import React from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../../components/Card';
import Button from '../../components/Button';
import Badge from '../../components/Badge';
import { mockCustomers } from '../../services/mockData';
import { Customer } from '../../types';

const CustomerListPage: React.FC = () => {
    const navigate = useNavigate();

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
            <h1 className="font-sans font-bold text-gray-900 leading-tight text-2xl sm:text-3xl">Customer Mastery</h1>
            <p className="mt-1 font-sans text-base text-gray-600">View and manage customer records.</p>
        </div>
        <Button variant="primary">Create New Customer</Button>
      </div>

      <Card className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
            <thead className="bg-gray-50 text-xs font-medium text-gray-600 uppercase tracking-wider border-b border-gray-200">
                <tr>
                    <th className="p-4">Customer ID</th>
                    <th className="p-4">Name</th>
                    <th className="p-4">Email</th>
                    <th className="p-4">KYC Status</th>
                    <th className="p-4">Onboarded</th>
                    <th className="p-4"></th>
                </tr>
            </thead>
            <tbody className="text-sm text-gray-800">
                {mockCustomers.map((customer: Customer) => (
                    <tr key={customer.id} className="border-b border-gray-200 last:border-b-0 hover:bg-gray-50 cursor-pointer" onClick={() => navigate(`/customers/${customer.id}`)}>
                        <td className="p-4 font-mono text-gray-600">{customer.customerId}</td>
                        <td className="p-4 font-medium">{customer.name}</td>
                        <td className="p-4">{customer.email}</td>
                        <td className="p-4"><Badge status={customer.kycStatus} /></td>
                        <td className="p-4">{customer.onboardedDate}</td>
                        <td className="p-4 text-right">
                           <Button variant="link" onClick={(e) => { e.stopPropagation(); navigate(`/customers/${customer.id}`)}}>View</Button>
                        </td>
                    </tr>
                ))}
            </tbody>
        </table>
      </Card>
    </div>
  );
};

export default CustomerListPage;