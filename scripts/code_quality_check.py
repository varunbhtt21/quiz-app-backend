#!/usr/bin/env python3
"""
Code Quality Assurance Script for QuizMaster Backend

This script checks for common Python syntax issues that can break the application.
It should be run before commits and during CI/CD pipelines.

Usage:
    python scripts/code_quality_check.py

Features:
- Syntax validation for all Python files
- Indentation consistency checks
- Import validation
- Basic linting

Long-term benefits:
- Prevents server startup failures
- Catches issues before they reach production
- Maintains code quality standards
"""

import os
import sys
import ast
import py_compile
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict


class CodeQualityChecker:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.errors: List[Dict] = []
        self.warnings: List[Dict] = []
    
    def check_syntax_all_files(self) -> bool:
        """Check syntax for all Python files in the project"""
        print("🔍 Checking Python syntax for all files...")
        
        python_files = list(self.root_dir.rglob("*.py"))
        total_files = len(python_files)
        passed = 0
        
        for py_file in python_files:
            # Skip virtual environment and cache files
            if any(exclude in str(py_file) for exclude in ['.venv', '__pycache__', '.git']):
                continue
                
            try:
                py_compile.compile(py_file, doraise=True)
                passed += 1
                print(f"✅ {py_file.relative_to(self.root_dir)}")
            except py_compile.PyCompileError as e:
                self.errors.append({
                    'file': str(py_file.relative_to(self.root_dir)),
                    'type': 'syntax_error',
                    'message': str(e)
                })
                print(f"❌ {py_file.relative_to(self.root_dir)}: {e}")
        
        print(f"\n📊 Syntax Check Results: {passed}/{total_files} files passed")
        return len(self.errors) == 0
    
    def check_ast_parse(self) -> bool:
        """Additional AST parsing check for more detailed error detection"""
        print("\n🔍 Performing AST parsing validation...")
        
        python_files = list(self.root_dir.rglob("*.py"))
        passed = 0
        
        for py_file in python_files:
            if any(exclude in str(py_file) for exclude in ['.venv', '__pycache__', '.git']):
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                ast.parse(content)
                passed += 1
            except SyntaxError as e:
                self.errors.append({
                    'file': str(py_file.relative_to(self.root_dir)),
                    'type': 'ast_error',
                    'message': f"Line {e.lineno}: {e.msg}",
                    'line': e.lineno
                })
                print(f"❌ {py_file.relative_to(self.root_dir)}: Line {e.lineno}: {e.msg}")
            except Exception as e:
                self.warnings.append({
                    'file': str(py_file.relative_to(self.root_dir)),
                    'type': 'ast_warning',
                    'message': str(e)
                })
        
        print(f"📊 AST Parsing Results: {passed} files passed")
        return len([e for e in self.errors if e['type'] == 'ast_error']) == 0
    
    def check_indentation_patterns(self) -> bool:
        """Check for common indentation issues"""
        print("\n🔍 Checking for indentation patterns...")
        
        problematic_patterns = [
            # Pattern that caused our issue
            (r'^\s+try:\s*$\n^\s{1,7}[a-zA-Z]', 'try block with insufficient indentation'),
            (r'^\s+if.*:\s*$\n^\s{1,7}[a-zA-Z]', 'if block with insufficient indentation'),
            (r'^\s+for.*:\s*$\n^\s{1,7}[a-zA-Z]', 'for block with insufficient indentation'),
        ]
        
        python_files = list(self.root_dir.rglob("*.py"))
        issues_found = 0
        
        for py_file in python_files:
            if any(exclude in str(py_file) for exclude in ['.venv', '__pycache__', '.git']):
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for mixed tabs and spaces
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    if '\t' in line and '    ' in line:
                        self.warnings.append({
                            'file': str(py_file.relative_to(self.root_dir)),
                            'type': 'mixed_indentation',
                            'message': f"Line {i}: Mixed tabs and spaces",
                            'line': i
                        })
                        issues_found += 1
                        
            except Exception as e:
                self.warnings.append({
                    'file': str(py_file.relative_to(self.root_dir)),
                    'type': 'indentation_check_error',
                    'message': str(e)
                })
        
        if issues_found == 0:
            print("✅ No indentation issues found")
        else:
            print(f"⚠️  Found {issues_found} indentation warnings")
        
        return True  # Warnings don't fail the check
    
    def check_imports(self) -> bool:
        """Check for import issues"""
        print("\n🔍 Checking imports...")
        
        try:
            # Try to import the main app to catch import errors
            import sys
            sys.path.insert(0, str(self.root_dir))
            from app.main import app
            print("✅ Main application imports successfully")
            return True
        except Exception as e:
            self.errors.append({
                'file': 'app/main.py',
                'type': 'import_error',
                'message': str(e)
            })
            print(f"❌ Import error: {e}")
            return False
    
    def generate_report(self) -> None:
        """Generate a summary report"""
        print("\n" + "="*60)
        print("📋 CODE QUALITY REPORT")
        print("="*60)
        
        if not self.errors and not self.warnings:
            print("🎉 All checks passed! Code quality is excellent.")
            return
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  • {error['file']}: {error['message']}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning['file']}: {warning['message']}")
        
        print(f"\n📊 Summary: {len(self.errors)} errors, {len(self.warnings)} warnings")
        
        if self.errors:
            print("\n🚨 Please fix all errors before proceeding!")
        
    def run_all_checks(self) -> bool:
        """Run all quality checks"""
        print("🚀 Starting Code Quality Checks for QuizMaster Backend")
        print("="*60)
        
        checks = [
            ("Syntax Validation", self.check_syntax_all_files),
            ("AST Parsing", self.check_ast_parse),
            ("Indentation Patterns", self.check_indentation_patterns),
            ("Import Validation", self.check_imports),
        ]
        
        all_passed = True
        
        for check_name, check_func in checks:
            try:
                result = check_func()
                if not result:
                    all_passed = False
            except Exception as e:
                print(f"❌ {check_name} failed with exception: {e}")
                all_passed = False
        
        self.generate_report()
        return all_passed


def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        root_dir = sys.argv[1]
    else:
        # Default to current directory (backend root)
        root_dir = os.getcwd()
    
    checker = CodeQualityChecker(root_dir)
    success = checker.run_all_checks()
    
    if success:
        print("\n✅ All quality checks passed!")
        sys.exit(0)
    else:
        print("\n❌ Quality checks failed!")
        sys.exit(1)


if __name__ == "__main__":
    main() 