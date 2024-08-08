from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/razorpay_callback', methods=['POST'])
def razorpay_callback():
    # Handle the callback data here
    payment_id = request.form.get('razorpay_payment_id')
    order_id = request.form.get('razorpay_order_id')
    signature = request.form.get('razorpay_signature')

    # Verify the signature to ensure the request is from Razorpay
    # You need to implement the verification logic here

    # If verification is successful, you can proceed with further actions
    # For example, you can set a flag in a database or a file to indicate payment success

    return jsonify(success=True), 200

if __name__ == '__main__':
    app.run(port=5000)