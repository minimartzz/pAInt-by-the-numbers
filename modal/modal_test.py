import modal

app = modal.App("My-Example-App")

@app.function()
def square(x):
  print("This code is running on a remote worker!")
  return x ** 2

@app.local_entrypoint()
def main():
  print("The square is: ", square.remote(42))