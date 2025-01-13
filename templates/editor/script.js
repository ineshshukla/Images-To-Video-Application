var draggables = document.querySelectorAll('[draggable="true"]');
var dropzone = document.querySelector('[dropzone="move"]');
var timeline = document.getElementById('timeline');

let timelineElements = [];

draggables.forEach(function(draggable) {
    draggable.addEventListener('dragstart', (e) => {
        e.dataTransfer.setData('text/plain', e.target.outerHTML);
    });
});

dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
});

dropzone.addEventListener('drop', (e) => {
    // check if dragged object is an image
    if (e.dataTransfer.getData('text/plain').includes('img')) {
        e.preventDefault();
        var temp = document.getElementById('temp');
        if (temp) temp.remove();
        var data = e.dataTransfer.getData('text/plain');
        var tempDiv = document.createElement('div');
        tempDiv.className = 'pic-element relative';
        var time = document.createElement('input');
        time.className = 'time bg-gray-800 p-2 rounded absolute top-1 right-1';
        time.value = '1s';
        var Delete = document.createElement('div');
        Delete.className = 'delete bg-red-500 px-1.5 py-1 rounded absolute top-1 left-1 hover:bg-red-600';
        Delete.innerHTML = '<i class="fa-solid fa-trash"></i>';
        tempDiv.innerHTML = data;
        tempDiv.appendChild(time);
        tempDiv.appendChild(Delete);
        dropzone.appendChild(tempDiv);
    }
});

var audioSelect = document.getElementById('audio-select');

fetch('/app/get_audio_files')
.then(response => response.json())
.then(data => {
    data.forEach(audio => {
        var option = document.createElement('option');
        option.value = audio.id;
        option.textContent = audio.name;
        audioSelect.appendChild(option);
    });
})
.catch(error => console.error('Error fetching audio files:', error));

document.addEventListener('click', (e) => {
    if (e.target.classList.contains('delete')) {
        e.target.parentElement.remove();
        while (timeline.firstElementChild && timeline.firstElementChild.classList.contains('transition') && timeline.firstElementChild.textContent.includes('Out')) {
            timeline.firstElementChild.remove();
        }
    } else if (e.target.parentElement.classList.contains('delete')) {
        e.target.parentElement.parentElement.remove();
    } 
});

const applyTransition = (transition) => {
    var lastElement = timeline.lastElementChild;
    if (lastElement) {
        // create a new div element
        var transitionDiv = document.createElement('div');

        transitionDiv.textContent = transition;
        transitionDiv.className = 'transition bg-purple-500 p-2 mr-1 rounded relative pl-9';

        var Delete = document.createElement('div');
        Delete.className = 'delete bg-red-500 px-1.5 py-1 rounded absolute top-1 left-1 hover:bg-red-600';
        Delete.innerHTML = '<i class="fa-solid fa-trash"></i>';
        transitionDiv.appendChild(Delete);

        timeline.appendChild(transitionDiv);
    }
    // } else if (lastElement.tagName) {
    //     var Delete = document.createElement('div');
    //     var transitionDiv = lastElement;
    //     Delete.className = 'delete bg-red-500 px-1.5 py-1 rounded absolute top-1 left-1 hover:bg-red-600';
    //     Delete.innerHTML = '<i class="fa-solid fa-trash"></i>';
    //     transitionDiv.remove();
    //     transitionDiv.textContent = transition;
    //     transitionDiv.appendChild(Delete);
    //     timeline.appendChild(transitionDiv)
    // }
}

var video = document.getElementById('video');
var playButton = document.getElementById('play-pause');
var seekBar = document.getElementById('seek-bar');
var currentTime = document.getElementById('current-time');

playButton.addEventListener('click', () => {
    if (video.paused == true) {
        video.play();
        playButton.innerHTML = '<i class="fa-solid fa-pause"></i>';
    } else {
        video.pause();
        playButton.innerHTML = '<i class="fa-solid fa-play"></i>';
    }
});

video.addEventListener('timeupdate', () => {
    var value = (100 / video.duration) * video.currentTime;
    seekBar.value = value;
    currentTime.innerHTML = formatTime(video.currentTime);
});

seekBar.addEventListener('change', () => {
    var time = video.duration * (seekBar.value / 100);
    video.currentTime = time;
});

const formatTime = (time) => {
    var minutes = Math.floor(time / 60);
    var seconds = Math.floor(time - minutes * 60);
    var minuteValue;
    var secondValue;

    if (minutes < 10) {
        minuteValue = "0" + minutes;
    } else {
        minuteValue = minutes;
    }

    if (seconds < 10) {
        secondValue = "0" + seconds;
    } else {
        secondValue = seconds;
    }

    return minuteValue + ":" + secondValue;
}

// rewind
var rewindButton = document.getElementById('rewind');
rewindButton.addEventListener('click', () => {
    video.currentTime = 0;
});

var uploadSound = document.getElementById('upload-sound');
var fileInput = document.getElementById('file-input');

// uploadSound.addEventListener('dragover', (e) => {
//     e.preventDefault();
//     uploadSound.classList.add('bg-purple-100');
// });

// uploadSound.addEventListener('dragleave', () => {
//     uploadSound.classList.remove('bg-purple-100');
// });

// uploadSound.addEventListener('drop', (e) => {
//     e.preventDefault();
//     fileInput.files = e.dataTransfer.files;
//     uploadSound.classList.remove('bg-purple-100');
// });

// fileInput.addEventListener('change', () => {
//     uploadSound.innerHTML = fileInput.files[0].name;
// });

let timeoutId = null;
let delay = 3000;  // Delay in milliseconds, adjust as needed

let callback = (mutationsList, observer) => {
    // If a timeout is already scheduled, clear it
    if (timeoutId !== null) {
        clearTimeout(timeoutId);
    }

    // Set a new timeout
    timeoutId = setTimeout(() => {
        for(let mutation of mutationsList) {
            timelineElements = [];
            for (var i = 0; i < timeline.children.length; i++) {
                if (timeline.children[i].classList.contains('pic-element')) {
                    timelineElements.push(`img:${timeline.children[i].querySelector('img').id}:${timeline.children[i].querySelector('input').value}`);
                    console.log(timelineElements);
                } else if (timeline.children[i].classList.contains('transition')) {
                    timelineElements.push(`trn:${timeline.children[i].textContent.replace(/\s/g, '')}`);
                    console.log(timelineElements);
                }
            }
            let formData = new FormData();
            formData.append('timeline', JSON.stringify(timelineElements));
            formData.append('audio', audioSelect.value);
            var width = document.getElementById('width').value || 1920;
            var height = document.getElementById('height').value || 1080;
            var quality = document.getElementById('quality').value || "5000k";
            formData.append('width', width);
            formData.append('height', height);
            formData.append('quality', quality);
            // send post request, then change video src to the response
            fetch('/app/preview', {
                method: 'POST',
                body: formData
            })
            .then(response => response.blob())
            .then(videoBlob => {
                const videoUrl = URL.createObjectURL(videoBlob);
                video.src = videoUrl;
            })
        }
    }, delay);
};

// Create an observer instance linked to the callback function
let observer = new MutationObserver(callback);

// Start observing the target node for configured mutations
observer.observe(timeline, { childList: true });

const downloadVid = () => {
    // download the video that is currently playing
    fetch(video.src)
    .then(response => response.blob())
    .then(videoBlob => {
        const videoUrl = URL.createObjectURL(videoBlob);
        const a = document.createElement('a');
        a.href = videoUrl;
        a.download = 'video.mp4';
        a.click();
    });
}