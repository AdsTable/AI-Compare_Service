# deepseek_validator.py
import os
import time
import warnings
import json
import litellm
from dotenv import load_dotenv
from termcolor import colored

# Suppress warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

# Load environment variables
load_dotenv()

class DeepSeekValidator:
    def __init__(self):
        self.api_key = os.getenv("Deepseek_API_KEY")
        self.model = "deepseek/deepseek-chat"
        self.results = {
            "connection_test": {"status": "pending", "response": None, "latency": None},
            "complex_query_test": {"status": "pending", "response": None, "latency": None},
            "function_calling_test": {"status": "pending", "response": None, "latency": None},
            "long_context_test": {"status": "pending", "response": None, "latency": None}
        }
        self.total_tokens = 0
        self.total_cost = 0.0
        
    def _make_request(self, messages, test_name, functions=None):
        """Make API request with timing and error handling"""
        try:
            start_time = time.time()
            
            response = litellm.completion(
                model=self.model,
                api_key=self.api_key,
                messages=messages,
                functions=functions,
                max_tokens=400
            )
            
            latency = time.time() - start_time
            content = response.choices[0].message.content
            usage = response.usage
            
            # Calculate cost (DeepSeek pricing: $0.001/1K input tokens, $0.002/1K output tokens)
            input_cost = (usage.prompt_tokens / 1000) * 0.001
            output_cost = (usage.completion_tokens / 1000) * 0.002
            cost = input_cost + output_cost
            
            self.total_tokens += usage.total_tokens
            self.total_cost += cost
            
            return {
                "status": "success",
                "response": content,
                "function_call": response.choices[0].message.function_call if hasattr(response.choices[0].message, 'function_call') else None,
                "latency": f"{latency:.2f}s",
                "tokens": usage.total_tokens,
                "cost": f"${cost:.6f}"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "response": str(e),
                "latency": None,
                "tokens": 0,
                "cost": "$0.00"
            }
    
    def run_connection_test(self):
        """Basic connection test"""
        messages = [{"role": "user", "content": "Respond with just 'API Ready'"}]
        self.results["connection_test"] = self._make_request(messages, "connection_test")
    
    def run_complex_query_test(self):
        """Test complex reasoning capability"""
        query = (
            "Compare the economic theories of Keynes and Hayek in 3 key points. "
            "Format your response as a numbered list with no introduction."
        )
        messages = [{"role": "user", "content": query}]
        self.results["complex_query_test"] = self._make_request(messages, "complex_query_test")
    
    def run_function_calling_test(self):
        """Test function calling capability"""
        functions = [
            {
                "name": "get_current_weather",
                "description": "Get the current weather in a given location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g. San Francisco, CA",
                        },
                        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                    },
                    "required": ["location"],
                },
            }
        ]
        
        messages = [{"role": "user", "content": "What's the weather like in Boston today?"}]
        self.results["function_calling_test"] = self._make_request(
            messages, "function_calling_test", functions
        )
    
    def run_long_context_test(self):
        """Test long context handling"""
        # Generate a long context with repeated patterns
        long_context = "The key concept is resilience. " * 50
        query = (
            f"{long_context}\n\nBased on the above text, what is the single most repeated concept? "
            "Respond with just the concept name."
        )
        
        messages = [{"role": "user", "content": query}]
        self.results["long_context_test"] = self._make_request(messages, "long_context_test")
    
    def run_all_tests(self):
        """Execute all validation tests"""
        print("🚀 Starting DeepSeek API Validation Suite")
        print(f"🔑 Using model: {self.model}")
        
        tests = [
            self.run_connection_test,
            self.run_complex_query_test,
            self.run_function_calling_test,
            self.run_long_context_test
        ]
        
        for i, test in enumerate(tests):
            print(f"\n🔍 Running test {i+1}/{len(tests)}...")
            test()
            time.sleep(1)  # Rate limit protection
        
        self.display_results()
    
    def display_results(self):
        """Display comprehensive test results"""
        print("\n" + "="*60)
        print("📊 DeepSeek API Validation Report")
        print("="*60)
        
        for test_name, result in self.results.items():
            status = result["status"]
            color = "green" if status == "success" else "red"
            symbol = "✅" if status == "success" else "❌"
            
            print(f"\n{symbol} {test_name.replace('_', ' ').title()}:")
            print(f"   Status: {colored(status.upper(), color)}")
            print(f"   Latency: {result['latency'] or 'N/A'}")
            
            if status == "success":
                if test_name == "function_calling_test" and result.get("function_call"):
                    print("   Function Call Detected:")
                    print(f"      Name: {result['function_call'].get('name')}")
                    print(f"      Arguments: {result['function_call'].get('arguments')}")
                else:
                    print(f"   Response: {result['response'][:200] + '...' if len(result['response']) > 200 else result['response']}")
            else:
                print(f"   Error: {result['response']}")
            
            print(f"   Tokens Used: {result['tokens']}")
            print(f"   Cost: {result['cost']}")
        
        print("\n" + "-"*60)
        print(f"🔢 Total Tokens Used: {self.total_tokens}")
        print(f"💵 Estimated Total Cost: ${self.total_cost:.6f}")
        print("="*60)
        
        # Final recommendation
        failed_tests = sum(1 for r in self.results.values() if r["status"] != "success")
        if failed_tests == 0:
            print(colored("\n🎉 All tests passed! API is fully functional.", "green"))
        else:
            print(colored(f"\n⚠️ {failed_tests} test(s) failed. Check error details above.", "yellow"))

if __name__ == "__main__":
    validator = DeepSeekValidator()
    validator.run_all_tests()