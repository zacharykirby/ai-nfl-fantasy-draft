#!/usr/bin/env python3
"""
NFL Fantasy Draft Assistant - Complete Pipeline Test Suite

This script tests the entire pipeline end-to-end to ensure all components
work correctly together and individually.
"""

import os
import sys
import json
import time
import subprocess
import pandas as pd
from pathlib import Path
from datetime import datetime
import traceback

# Add the scripts directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import our modules
import data_ingest
import news_fetcher
import news_analyzer
import ranker
import cli

class PipelineTester:
    def __init__(self):
        self.test_results = {}
        self.start_time = time.time()
        self.base_dir = Path(__file__).parent.parent
        
        # Test directories
        self.data_dir = self.base_dir / "data"
        self.news_dir = self.base_dir / "news"
        self.outputs_dir = self.base_dir / "outputs"
        
        # Test files
        self.test_data_file = self.data_dir / "test_player_stats.csv"
        self.test_news_file = self.news_dir / "test_raw_headlines.json"
        self.test_features_file = self.news_dir / "test_player_features.json"
        self.test_rankings_file = self.outputs_dir / "test_rankings.json"
        
        print("🏈 NFL Fantasy Draft Assistant - Pipeline Test Suite")
        print("=" * 60)
        
    def log_test(self, test_name, status, message=""):
        """Log test results"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} [{timestamp}] {test_name}: {message}")
        
        self.test_results[test_name] = {
            "status": status,
            "message": message,
            "timestamp": timestamp
        }
        
    def test_data_ingest(self):
        """Test the data ingestion module"""
        print("\n📊 Testing Data Ingestion Module...")
        
        try:
            # Test data collection
            print("  - Testing data collection...")
            ingester = data_ingest.FantasyDataIngester()
            player_data = ingester.get_fantasy_data()
            
            if player_data is None or player_data.empty:
                self.log_test("Data Collection", False, "No data returned")
                return False
                
            self.log_test("Data Collection", True, f"Collected {len(player_data)} players")
            
            # Test data validation
            print("  - Testing data validation...")
            required_columns = ['player_name', 'position', 'team', 'season']
            missing_columns = [col for col in required_columns if col not in player_data.columns]
            
            if missing_columns:
                self.log_test("Data Validation", False, f"Missing columns: {missing_columns}")
                return False
                
            self.log_test("Data Validation", True, "All required columns present")
            
            # Test data quality
            print("  - Testing data quality...")
            null_counts = player_data[required_columns].isnull().sum()
            if null_counts.sum() > 0:
                self.log_test("Data Quality", False, f"Null values found: {null_counts.to_dict()}")
                return False
                
            self.log_test("Data Quality", True, "No null values in required fields")
            
            # Test file output
            print("  - Testing file output...")
            test_file = self.data_dir / "test_player_stats.csv"
            player_data.to_csv(test_file, index=False)
            
            if test_file.exists():
                self.log_test("File Output", True, f"Data saved to {test_file}")
            else:
                self.log_test("File Output", False, "Failed to save data file")
                return False
                
            return True
            
        except Exception as e:
            self.log_test("Data Ingestion", False, f"Error: {str(e)}")
            return False
    
    def test_news_fetcher(self):
        """Test the news fetching module"""
        print("\n📰 Testing News Fetching Module...")
        
        try:
            # Test headline fetching
            print("  - Testing headline fetching...")
            headlines = news_fetcher.fetch_headlines()
            
            if not headlines:
                self.log_test("Headline Fetching", False, "No headlines returned")
                return False
                
            self.log_test("Headline Fetching", True, f"Fetched {len(headlines)} headlines")
            
            # Test headline structure
            print("  - Testing headline structure...")
            required_fields = ['title', 'summary', 'link', 'published']
            sample_headline = headlines[0]
            
            missing_fields = [field for field in required_fields if field not in sample_headline]
            if missing_fields:
                self.log_test("Headline Structure", False, f"Missing fields: {missing_fields}")
                return False
                
            self.log_test("Headline Structure", True, "All required fields present")
            
            # Test file output
            print("  - Testing file output...")
            test_file = self.news_dir / "test_raw_headlines.json"
            with open(test_file, 'w') as f:
                json.dump(headlines, f, indent=2, default=str)
                
            if test_file.exists():
                self.log_test("News File Output", True, f"Headlines saved to {test_file}")
            else:
                self.log_test("News File Output", False, "Failed to save headlines file")
                return False
                
            return True
            
        except Exception as e:
            self.log_test("News Fetching", False, f"Error: {str(e)}")
            return False
    
    def test_news_analyzer(self):
        """Test the news analysis module"""
        print("\n🧠 Testing News Analysis Module...")
        
        try:
            # Test with sample headlines
            print("  - Testing headline analysis...")
            test_headlines = [
                {
                    "title": "Christian McCaffrey expected to play in Week 1",
                    "summary": "49ers RB Christian McCaffrey is expected to be fully healthy for the season opener.",
                    "link": "https://example.com/news1",
                    "published": "2024-08-15"
                },
                {
                    "title": "Tyreek Hill dealing with minor injury",
                    "summary": "Dolphins WR Tyreek Hill is nursing a minor injury but should be ready for training camp.",
                    "link": "https://example.com/news2", 
                    "published": "2024-08-14"
                }
            ]
            
            # Save test headlines to file first
            test_headlines_file = self.news_dir / "test_headlines_for_analysis.json"
            with open(test_headlines_file, 'w') as f:
                json.dump(test_headlines, f, indent=2, default=str)
            
            # Test analysis using the file-based function
            news_analyzer.analyze_headlines(str(test_headlines_file), str(self.news_dir / "test_player_features.json"))
            
            # Check if output file was created
            output_file = self.news_dir / "test_player_features.json"
            if not output_file.exists():
                self.log_test("Headline Analysis", False, "No output file created")
                return False
            
            # Load and validate the results
            with open(output_file, 'r') as f:
                features_data = json.load(f)
            
            features = features_data.get('player_features', {})
            if not features:
                self.log_test("Headline Analysis", False, "No features returned")
                return False
                
            self.log_test("Headline Analysis", True, f"Analyzed {len(features)} players")
            
            # Test feature structure
            print("  - Testing feature structure...")
            sample_player = list(features.values())[0]
            required_fields = ['avg_sentiment', 'avg_buzz', 'has_injury', 'all_topics']
            
            missing_fields = [field for field in required_fields if field not in sample_player]
            if missing_fields:
                self.log_test("Feature Structure", False, f"Missing fields: {missing_fields}")
                return False
                
            self.log_test("Feature Structure", True, "All required fields present")
            
            return True
            
        except Exception as e:
            self.log_test("News Analysis", False, f"Error: {str(e)}")
            return False
    
    def test_ranker(self):
        """Test the ranking module"""
        print("\n📈 Testing Ranking Module...")
        
        try:
            # Load test data
            print("  - Loading test data...")
            ingester = data_ingest.FantasyDataIngester()
            player_data = ingester.get_fantasy_data()
            
            if player_data is None or player_data.empty:
                self.log_test("Data Loading", False, "No player data available")
                return False
                
            self.log_test("Data Loading", True, f"Loaded {len(player_data)} players")
            
            # Create test news features
            print("  - Creating test news features...")
            test_features = {
                "Christian McCaffrey": {
                    "sentiment_score": 0.8,
                    "buzz_score": 0.9,
                    "injury_flag": False,
                    "topics": ["positive", "health", "performance"]
                },
                "Tyreek Hill": {
                    "sentiment_score": 0.6,
                    "buzz_score": 0.7,
                    "injury_flag": True,
                    "topics": ["injury", "recovery"]
                }
            }
            
            # Test ranking
            print("  - Testing ranking algorithm...")
            ranker_instance = ranker.PlayerRanker()
            rankings = ranker_instance.rank_players()
            
            if rankings is None or rankings.empty:
                self.log_test("Ranking Algorithm", False, "No rankings returned")
                return False
                
            self.log_test("Ranking Algorithm", True, f"Ranked {len(rankings)} players")
            
            # Test ranking structure
            print("  - Testing ranking structure...")
            required_columns = ['player', 'position', 'team', 'total_score', 'tier']
            missing_columns = [col for col in required_columns if col not in rankings.columns]
            
            if missing_columns:
                self.log_test("Ranking Structure", False, f"Missing columns: {missing_columns}")
                return False
                
            self.log_test("Ranking Structure", True, "All required columns present")
            
            # Test file output
            print("  - Testing file output...")
            test_file = self.outputs_dir / "test_rankings.json"
            rankings.to_json(test_file, orient='records', indent=2)
            
            if test_file.exists():
                self.log_test("Rankings File Output", True, f"Rankings saved to {test_file}")
            else:
                self.log_test("Rankings File Output", False, "Failed to save rankings file")
                return False
                
            return True
            
        except Exception as e:
            self.log_test("Ranking", False, f"Error: {str(e)}")
            return False
    
    def test_cli(self):
        """Test the CLI module"""
        print("\n🖥️ Testing CLI Module...")
        
        try:
            # Test CLI help
            print("  - Testing CLI help...")
            result = subprocess.run([
                sys.executable, "scripts/cli.py", "--help"
            ], capture_output=True, text=True, cwd=self.base_dir)
            
            if result.returncode == 0 and "position" in result.stdout:
                self.log_test("CLI Help", True, "Help command works correctly")
            else:
                self.log_test("CLI Help", False, "Help command failed")
                return False
            
            # Test CLI position filtering
            print("  - Testing CLI position filtering...")
            result = subprocess.run([
                sys.executable, "scripts/cli.py", "--rankings", "--position", "WR", "--top", "5"
            ], capture_output=True, text=True, cwd=self.base_dir)
            
            if result.returncode == 0:
                self.log_test("CLI Position Filter", True, "Position filtering works")
            else:
                self.log_test("CLI Position Filter", False, f"Position filtering failed: {result.stderr}")
                return False
            
            # Test CLI player search
            print("  - Testing CLI player search...")
            result = subprocess.run([
                sys.executable, "scripts/cli.py", "--player", "Christian McCaffrey"
            ], capture_output=True, text=True, cwd=self.base_dir)
            
            if result.returncode == 0:
                self.log_test("CLI Player Search", True, "Player search works")
            else:
                self.log_test("CLI Player Search", False, f"Player search failed: {result.stderr}")
                return False
                
            return True
            
        except Exception as e:
            self.log_test("CLI", False, f"Error: {str(e)}")
            return False
    
    def test_full_pipeline(self):
        """Test the complete pipeline workflow"""
        print("\n🔄 Testing Full Pipeline Workflow...")
        
        try:
            # Run the complete pipeline
            print("  - Running complete pipeline...")
            result = subprocess.run([
                sys.executable, "scripts/cli.py", "--pipeline"
            ], capture_output=True, text=True, cwd=self.base_dir)
            
            if result.returncode == 0:
                self.log_test("Full Pipeline", True, "Complete pipeline executed successfully")
            else:
                self.log_test("Full Pipeline", False, f"Pipeline failed: {result.stderr}")
                return False
            
            # Verify outputs were created
            print("  - Verifying pipeline outputs...")
            expected_files = [
                self.data_dir / "base_player_stats.csv",
                self.news_dir / "raw_headlines.json",
                self.news_dir / "player_features.json",
                self.outputs_dir / "ranking_summary.json"
            ]
            
            missing_files = [f for f in expected_files if not f.exists()]
            if missing_files:
                self.log_test("Pipeline Outputs", False, f"Missing files: {missing_files}")
                return False
                
            self.log_test("Pipeline Outputs", True, "All expected output files created")
            
            # Test CLI with pipeline results
            print("  - Testing CLI with pipeline results...")
            result = subprocess.run([
                sys.executable, "scripts/cli.py", "--rankings", "--position", "RB", "--top", "10"
            ], capture_output=True, text=True, cwd=self.base_dir)
            
            if result.returncode == 0:
                self.log_test("CLI with Pipeline Data", True, "CLI works with pipeline data")
            else:
                self.log_test("CLI with Pipeline Data", False, f"CLI failed with pipeline data: {result.stderr}")
                return False
                
            return True
            
        except Exception as e:
            self.log_test("Full Pipeline", False, f"Error: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting comprehensive pipeline testing...")
        
        # Test individual modules
        tests = [
            ("Data Ingestion", self.test_data_ingest),
            ("News Fetching", self.test_news_fetcher),
            ("News Analysis", self.test_news_analyzer),
            ("Ranking", self.test_ranker),
            ("CLI", self.test_cli),
            ("Full Pipeline", self.test_full_pipeline)
        ]
        
        all_passed = True
        for test_name, test_func in tests:
            try:
                if not test_func():
                    all_passed = False
            except Exception as e:
                self.log_test(test_name, False, f"Unexpected error: {str(e)}")
                all_passed = False
        
        # Generate test report
        self.generate_test_report(all_passed)
        
        return all_passed
    
    def generate_test_report(self, all_passed):
        """Generate a comprehensive test report"""
        print("\n" + "=" * 60)
        print("📋 TEST REPORT SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result["status"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if all_passed:
            print("\n🎉 ALL TESTS PASSED! Pipeline is working correctly.")
        else:
            print("\n⚠️  SOME TESTS FAILED. Please review the errors above.")
        
        # Save detailed report
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "success_rate": (passed_tests/total_tests)*100,
            "all_passed": all_passed,
            "test_results": self.test_results,
            "execution_time": time.time() - self.start_time
        }
        
        report_file = self.base_dir / "test_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
            
        print(f"\n📄 Detailed report saved to: {report_file}")
        
        # Print failed tests
        if failed_tests > 0:
            print("\n❌ FAILED TESTS:")
            for test_name, result in self.test_results.items():
                if not result["status"]:
                    print(f"  - {test_name}: {result['message']}")

def main():
    """Main test runner"""
    tester = PipelineTester()
    
    try:
        success = tester.run_all_tests()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n⏹️  Testing interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Unexpected error during testing: {str(e)}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main()) 