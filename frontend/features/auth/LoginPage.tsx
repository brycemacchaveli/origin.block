import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import Button from '../../components/Button';
import Input from '../../components/Input';
import Logo from '../../components/Logo';

const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const [email, setEmail] = useState('admin@veridian.io');
  const [password, setPassword] = useState('password');
  const navigate = useNavigate();

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    login(() => {
      navigate('/');
    });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-sm w-full bg-white p-8 rounded-lg shadow-lg">
        <div className="text-center mb-8">
          <div className="inline-block">
            <Logo />
          </div>
          <h2 className="mt-6 font-sans font-bold text-gray-900 leading-tight text-2xl sm:text-3xl">
            Welcome Back
          </h2>
          <p className="mt-2 font-sans text-base text-gray-600">
            Secure Access to Your Financial Platform
          </p>
        </div>
        <form onSubmit={handleLogin} className="space-y-6">
          <Input 
            id="email" 
            label="Email" 
            type="email" 
            value={email} 
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required 
          />
          <Input 
            id="password" 
            label="Password" 
            type="password" 
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required 
          />
          <div className="flex items-center justify-between">
             <div className="text-sm">
                <a href="#" className="font-medium text-brand-primary hover:underline">
                    Forgot Password?
                </a>
            </div>
          </div>
          <Button type="submit" variant="primary" className="w-full">
            Login
          </Button>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;