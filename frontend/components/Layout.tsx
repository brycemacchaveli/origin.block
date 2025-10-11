import React, { useState, Fragment } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import Logo from './Logo';
import { MenuIcon, XIcon, UserIcon, LogoutIcon } from './icons';
import { NAV_LINKS } from '../constants';

const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const NavContent = () => (
    <nav className="flex flex-col space-y-2 mt-8">
      {NAV_LINKS.map((item) => (
        <NavLink
          key={item.name}
          to={item.href}
          onClick={() => setMobileMenuOpen(false)}
          className={({ isActive }: { isActive: boolean }) =>
            `px-4 py-2.5 rounded-lg text-base font-medium transition-colors duration-200 ${
              isActive
                ? 'bg-brand-primary text-white'
                : 'text-gray-700 hover:bg-gray-100 hover:text-brand-primary'
            }`
          }
        >
          {item.name}
        </NavLink>
      ))}
    </nav>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile Off-Canvas Menu */}
      <div
        className={`fixed inset-0 z-50 transform ${
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
        } transition-transform duration-300 ease-in-out lg:hidden`}
      >
        <div className="fixed inset-0 bg-black bg-opacity-25" onClick={() => setMobileMenuOpen(false)}></div>
        <div className="relative w-64 h-full bg-white shadow-lg p-6">
          <button
            onClick={() => setMobileMenuOpen(false)}
            className="absolute top-6 right-6 text-gray-600"
          >
            <XIcon className="w-6 h-6" />
          </button>
          <div className="mb-8">
             <Logo />
          </div>
          <NavContent />
        </div>
      </div>

      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex lg:flex-col lg:w-64 lg:fixed lg:inset-y-0 lg:border-r lg:border-gray-200 lg:bg-white lg:pt-8 lg:pb-6 px-6">
        <div className="mb-10">
            <Logo />
        </div>
        <NavContent />
      </aside>

      {/* Main Content */}
      <div className="lg:pl-64 flex flex-col flex-1">
        {/* Header */}
        <header className="sticky top-0 z-40 lg:z-10 bg-white/75 backdrop-blur-sm shadow-sm">
          <div className="max-w-screen-xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-16">
              {/* Hamburger for mobile */}
              <div className="lg:hidden">
                <button
                  onClick={() => setMobileMenuOpen(true)}
                  className="text-gray-800"
                >
                  <MenuIcon className="h-6 w-6" />
                </button>
              </div>

              {/* Spacer on desktop */}
              <div className="hidden lg:block"></div>

              {/* Profile dropdown */}
              <div className="relative">
                <button
                  onClick={() => setProfileMenuOpen(!profileMenuOpen)}
                  className="flex items-center space-x-2 p-2 rounded-full hover:bg-gray-100"
                >
                  <UserIcon className="h-6 w-6 text-gray-600" />
                  <span className="hidden sm:inline text-sm font-medium text-gray-700">{user?.name}</span>
                </button>
                {profileMenuOpen && (
                  <div className="origin-top-right absolute right-0 mt-2 w-48 rounded-md shadow-lg py-1 bg-white ring-1 ring-black ring-opacity-5">
                    <button
                      onClick={handleLogout}
                      className="w-full text-left flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                    >
                      <LogoutIcon className="w-4 h-4 mr-2" />
                      Logout
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>

        <main className="flex-1 pb-8">
          <div className="max-w-screen-xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 lg:py-12">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};

export default Layout;