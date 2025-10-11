import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Card from '../../components/Card';
import Button from '../../components/Button';
import Badge from '../../components/Badge';
import { mockLoans } from '../../services/mockData';
import { Loan } from '../../types';

const LoanListPage: React.FC = () => {
    const navigate = useNavigate();

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
            <h1 className="font-sans font-bold text-gray-900 leading-tight text-2xl sm:text-3xl">Loan Origination</h1>
            <p className="mt-1 font-sans text-base text-gray-600">Manage and track all loan applications.</p>
        </div>
        <Link to="/loans/new">
            <Button variant="primary">New Loan Application</Button>
        </Link>
      </div>

      <Card className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
            <thead className="bg-gray-50 text-xs font-medium text-gray-600 uppercase tracking-wider border-b border-gray-200">
                <tr>
                    <th className="p-4">Loan ID</th>
                    <th className="p-4">Applicant</th>
                    <th className="p-4">Amount</th>
                    <th className="p-4">Status</th>
                    <th className="p-4">Submitted</th>
                    <th className="p-4"></th>
                </tr>
            </thead>
            <tbody className="text-sm text-gray-800">
                {mockLoans.map((loan: Loan) => (
                    <tr key={loan.id} className="border-b border-gray-200 last:border-b-0 hover:bg-gray-50 cursor-pointer" onClick={() => navigate(`/loans/${loan.id}`)}>
                        <td className="p-4 font-mono text-gray-600">{loan.id}</td>
                        <td className="p-4 font-medium">{loan.applicantName}</td>
                        <td className="p-4">{`$${loan.amount.toLocaleString()}`}</td>
                        <td className="p-4"><Badge status={loan.status} /></td>
                        <td className="p-4">{loan.submittedDate}</td>
                        <td className="p-4 text-right">
                           <Button variant="link" onClick={(e) => { e.stopPropagation(); navigate(`/loans/${loan.id}`)}}>View</Button>
                        </td>
                    </tr>
                ))}
            </tbody>
        </table>
      </Card>
    </div>
  );
};

export default LoanListPage;