#!/usr/bin/env python3
"""
Test Runner for Shakshuka Task Manager
Runs comprehensive test suites and generates reports
"""

import unittest
import sys
import os
import time
import json
from datetime import datetime

# Add the parent directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_unit_tests():
    """Run unit tests"""
    print("=" * 60)
    print("RUNNING UNIT TESTS")
    print("=" * 60)
    
    # Import unit tests
    from tests.test_unit import (
        TestSQLiteDataManager,
        TestSecurityManager,
        TestPerformanceMonitor,
        TestUserManager,
        TestIntegration
    )
    
    # Create unit test suite (use modern loader; unittest.makeSuite is deprecated/removed)
    loader = unittest.defaultTestLoader
    unit_suite = unittest.TestSuite()
    unit_suite.addTests(loader.loadTestsFromTestCase(TestSQLiteDataManager))
    unit_suite.addTests(loader.loadTestsFromTestCase(TestSecurityManager))
    unit_suite.addTests(loader.loadTestsFromTestCase(TestPerformanceMonitor))
    unit_suite.addTests(loader.loadTestsFromTestCase(TestUserManager))
    unit_suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run unit tests
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(unit_suite)
    
    return result

def run_integration_tests():
    """Run integration tests"""
    print("\n" + "=" * 60)
    print("RUNNING INTEGRATION TESTS")
    print("=" * 60)
    
    # Import integration tests
    from tests.test_integration import (
        TestAPIIntegration,
        TestPerformanceIntegration
    )
    
    # Create integration test suite (use modern loader)
    loader = unittest.defaultTestLoader
    integration_suite = unittest.TestSuite()
    integration_suite.addTests(loader.loadTestsFromTestCase(TestAPIIntegration))
    integration_suite.addTests(loader.loadTestsFromTestCase(TestPerformanceIntegration))
    
    # Run integration tests
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(integration_suite)
    
    return result

def generate_test_report(unit_result, integration_result):
    """Generate comprehensive test report"""
    report = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'unit_tests': {
                'total': unit_result.testsRun,
                'failures': len(unit_result.failures),
                'errors': len(unit_result.errors),
                'success_rate': ((unit_result.testsRun - len(unit_result.failures) - len(unit_result.errors)) / unit_result.testsRun * 100) if unit_result.testsRun > 0 else 0
            },
            'integration_tests': {
                'total': integration_result.testsRun,
                'failures': len(integration_result.failures),
                'errors': len(integration_result.errors),
                'success_rate': ((integration_result.testsRun - len(integration_result.failures) - len(integration_result.errors)) / integration_result.testsRun * 100) if integration_result.testsRun > 0 else 0
            },
            'overall': {
                'total_tests': unit_result.testsRun + integration_result.testsRun,
                'total_failures': len(unit_result.failures) + len(integration_result.failures),
                'total_errors': len(unit_result.errors) + len(integration_result.errors),
                'overall_success_rate': 0
            }
        },
        'details': {
            'unit_test_failures': [{'test': str(test), 'error': str(error)} for test, error in unit_result.failures],
            'unit_test_errors': [{'test': str(test), 'error': str(error)} for test, error in unit_result.errors],
            'integration_test_failures': [{'test': str(test), 'error': str(error)} for test, error in integration_result.failures],
            'integration_test_errors': [{'test': str(test), 'error': str(error)} for test, error in integration_result.errors]
        }
    }
    
    # Calculate overall success rate
    total_tests = report['summary']['overall']['total_tests']
    total_failures = report['summary']['overall']['total_failures']
    total_errors = report['summary']['overall']['total_errors']
    
    if total_tests > 0:
        report['summary']['overall']['overall_success_rate'] = ((total_tests - total_failures - total_errors) / total_tests * 100)
    
    return report

def save_report(report, filename='test_report.json'):
    """Save test report to file"""
    try:
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\nTest report saved to: {filename}")
    except Exception as e:
        print(f"Error saving test report: {e}")

def print_summary(report):
    """Print test summary"""
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    unit = report['summary']['unit_tests']
    integration = report['summary']['integration_tests']
    overall = report['summary']['overall']
    
    print(f"Unit Tests:")
    print(f"  - Total: {unit['total']}")
    print(f"  - Failures: {unit['failures']}")
    print(f"  - Errors: {unit['errors']}")
    print(f"  - Success Rate: {unit['success_rate']:.1f}%")
    
    print(f"\nIntegration Tests:")
    print(f"  - Total: {integration['total']}")
    print(f"  - Failures: {integration['failures']}")
    print(f"  - Errors: {integration['errors']}")
    print(f"  - Success Rate: {integration['success_rate']:.1f}%")
    
    print(f"\nOverall:")
    print(f"  - Total Tests: {overall['total_tests']}")
    print(f"  - Total Failures: {overall['total_failures']}")
    print(f"  - Total Errors: {overall['total_errors']}")
    print(f"  - Overall Success Rate: {overall['overall_success_rate']:.1f}%")
    
    # Determine overall status
    if overall['overall_success_rate'] >= 95:
        status = "✅ EXCELLENT"
    elif overall['overall_success_rate'] >= 90:
        status = "✅ GOOD"
    elif overall['overall_success_rate'] >= 80:
        status = "⚠️  ACCEPTABLE"
    else:
        status = "❌ NEEDS IMPROVEMENT"
    
    print(f"\nOverall Status: {status}")
    
    # Print failures and errors if any
    if overall['total_failures'] > 0 or overall['total_errors'] > 0:
        print(f"\nIssues Found:")
        
        if report['details']['unit_test_failures']:
            print(f"\nUnit Test Failures:")
            for failure in report['details']['unit_test_failures']:
                print(f"  - {failure['test']}")
        
        if report['details']['unit_test_errors']:
            print(f"\nUnit Test Errors:")
            for error in report['details']['unit_test_errors']:
                print(f"  - {error['test']}")
        
        if report['details']['integration_test_failures']:
            print(f"\nIntegration Test Failures:")
            for failure in report['details']['integration_test_failures']:
                print(f"  - {failure['test']}")
        
        if report['details']['integration_test_errors']:
            print(f"\nIntegration Test Errors:")
            for error in report['details']['integration_test_errors']:
                print(f"  - {error['test']}")

def main():
    """Main test runner"""
    print("Shakshuka Task Manager - Comprehensive Test Suite")
    print("=" * 60)
    
    start_time = time.time()
    
    try:
        # Run unit tests
        unit_result = run_unit_tests()
        
        # Run integration tests
        integration_result = run_integration_tests()
        
        # Generate report
        report = generate_test_report(unit_result, integration_result)
        
        # Print summary
        print_summary(report)
        
        # Save report
        save_report(report)
        
        # Calculate total time
        total_time = time.time() - start_time
        print(f"\nTotal test execution time: {total_time:.2f} seconds")
        
        # Return appropriate exit code
        if report['summary']['overall']['overall_success_rate'] >= 90:
            print("\n🎉 All tests passed successfully!")
            return 0
        else:
            print("\n⚠️  Some tests failed. Please review the report.")
            return 1
            
    except Exception as e:
        print(f"\n❌ Test runner error: {e}")
        return 1

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
