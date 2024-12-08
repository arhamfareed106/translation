document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const imagePreview = document.getElementById('imagePreview');
    const preview = document.getElementById('preview');
    const removeImageBtn = document.getElementById('removeImage');
    const processBtn = document.getElementById('processBtn');
    const resultsContainer = document.getElementById('resultsContainer');
    const loadingSpinner = document.getElementById('loadingSpinner');

    // Drag and drop handlers
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = '#2980b9';
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.style.borderColor = '#3498db';
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = '#3498db';
        handleFile(e.dataTransfer.files[0]);
    });

    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        handleFile(e.target.files[0]);
    });

    removeImageBtn.addEventListener('click', () => {
        clearImage();
    });

    processBtn.addEventListener('click', processImage);

    function handleFile(file) {
        if (file && file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (e) => {
                preview.src = e.target.result;
                imagePreview.classList.remove('hidden');
                dropZone.classList.add('hidden');
                processBtn.disabled = false;
            };
            reader.readAsDataURL(file);
        } else {
            alert('Please upload an image file.');
        }
    }

    function clearImage() {
        preview.src = '';
        imagePreview.classList.add('hidden');
        dropZone.classList.remove('hidden');
        processBtn.disabled = true;
        resultsContainer.classList.add('hidden');
        fileInput.value = '';
    }

    async function processImage() {
        const formData = new FormData();
        formData.append('image', fileInput.files[0]);

        loadingSpinner.classList.remove('hidden');
        processBtn.disabled = true;

        try {
            const response = await fetch('/process', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Server error');
            }

            const data = await response.json();
            displayResults(data);
        } catch (error) {
            alert('Error processing image: ' + error.message);
        } finally {
            loadingSpinner.classList.add('hidden');
            processBtn.disabled = false;
        }
    }

    function displayResults(data) {
        document.getElementById('originalText').textContent = data.original_text;
        document.getElementById('translatedText').textContent = data.translated_text;
        document.getElementById('nameField').textContent = data.parsed_fields.Name;
        document.getElementById('phoneField').textContent = data.parsed_fields.Phone;
        document.getElementById('addressField').textContent = data.parsed_fields.Address;
        document.getElementById('typeField').textContent = data.parsed_fields['Type of Information'];

        // Handle additional information
        const additionalInfoField = document.getElementById('additionalInfoField');
        const additionalInfoContent = document.getElementById('additionalInfo');
        
        if (data.parsed_fields['Additional Information']) {
            additionalInfoContent.textContent = data.parsed_fields['Additional Information'];
            additionalInfoField.style.display = 'block';
        } else {
            additionalInfoField.style.display = 'none';
        }

        resultsContainer.classList.remove('hidden');
    }
});
