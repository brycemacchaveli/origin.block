import React from 'react';
import { useParams, Link } from 'react-router-dom';
import Card from '../../components/Card';
import Button from '../../components/Button';
import Badge from '../../components/Badge';
import { mockCustomers, mockLoans } from '../../services/mockData';

const CustomerProfilePage: React.FC = () => {
    const { id } = useParams();
    const customer = mockCustomers.find(c => c.id === id);

    if (!customer) {
        return <p>Customer not found.</p>;
    }
    
    const loans = mockLoans.filter(loan => customer.associatedLoans.includes(loan.id));

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div>
                    <h1 className="font-sans font-bold text-gray-900 leading-tight text-2xl sm:text-3xl">{customer.name}</h1>
                    <div className="flex items-center space-x-2 mt-1">
                        <span className="font-mono text-sm text-gray-600">{customer.customerId}</span>
                        <Badge status={customer.kycStatus} />
                    </div>
                </div>
                <Button variant="secondary">Edit Profile</Button>
            </div>
            
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <Card className="lg:col-span-2">
                    <h3 className="font-sans font-semibold text-gray-800 text-lg mb-4">Personal Information</h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-gray-700">
                        <div><strong className="block text-gray-500 text-sm">Full Name:</strong> {customer.name}</div>
                        <div><strong className="block text-gray-500 text-sm">Email Address:</strong> {customer.email}</div>
                        <div><strong className="block text-gray-500 text-sm">Onboarded Date:</strong> {customer.onboardedDate}</div>
                    </div>

                    <h3 className="font-sans font-semibold text-gray-800 text-lg mt-8 mb-4">Consent Preferences</h3>
                     <div className="space-y-2">
                        <label className="flex items-center">
                            <input type="checkbox" className="h-4 w-4 text-brand-primary border-gray-300 rounded" defaultChecked />
                            <span className="ml-2 text-gray-700">Share data for marketing purposes.</span>
                        </label>
                        <label className="flex items-center">
                            <input type="checkbox" className="h-4 w-4 text-brand-primary border-gray-300 rounded" />
                            <span className="ml-2 text-gray-700">Allow third-party data sharing.</span>
                        </label>
                    </div>
                </Card>

                <Card>
                    <h3 className="font-sans font-semibold text-gray-800 text-lg mb-4">Associated Loans</h3>
                    <ul className="space-y-3">
                       {loans.map(loan => (
                            <li key={loan.id} className="p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
                                <Link to={`/loans/${loan.id}`} className="font-medium text-gray-800 hover:text-brand-primary">
                                    <div className="flex justify-between">
                                        <span>{loan.id}</span>
                                        <Badge status={loan.status} />
                                    </div>
                                    <div className="text-sm text-gray-600">${loan.amount.toLocaleString()}</div>
                                </Link>
                            </li>
                       ))}
                    </ul>
                </Card>
            </div>
        </div>
    );
};

export default CustomerProfilePage;